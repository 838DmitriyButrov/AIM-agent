"""Typed, evidence-oriented audit models: signals, not certified conclusions."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

AgentName = Literal["legal", "geo", "ux"]
FindingStatus = Literal["observation", "potential_risk", "needs_review", "passed", "not_tested"]
Severity = Literal["info", "low", "medium", "high"]
Applicability = Literal["applicable", "conditional", "unknown", "not_applicable"]
EvidenceLevel = Literal["direct", "indicative", "insufficient"]


class Evidence(BaseModel):
    page: str
    kind: str  # DOM / HTTP / browser / legal_source / expert_assessment
    detail: str
    selector: str | None = None
    source_sha256: str | None = None  # digest of the source page, not a copy of user data


class Finding(BaseModel):
    id: str  # stable rule + URL + issue key hash; repeat scans should preserve the ID
    agent: AgentName
    rule_id: str
    title: str
    explanation: str
    severity: Severity
    status: FindingStatus
    confidence: Literal["low", "medium", "high"]
    applicability: Applicability = "unknown"
    evidence_level: EvidenceLevel = "indicative"
    evidence: list[Evidence] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    action: str
    needs_human_review: bool = False


class AccessDiagnostic(BaseModel):
    """Minimal HTTP access evidence. Never stores cookies, auth tokens or response HTML."""
    phase: Literal["robots", "sitemap", "page"]
    url: str
    status_code: int
    response_class: Literal["authentication_or_policy", "forbidden", "rate_limited"]
    content_type: str = ""
    auth_schemes: list[str] = Field(default_factory=list)
    server_hint: str = "unknown"
    has_cdn_request_id: bool = False
    response_body_bytes: int = 0
    body_sha256: str = ""
    challenge_indicators: list[str] = Field(default_factory=list)
    interpretation: str = "Причина отказа не установлена. Не является SEO/LEGAL-находкой."


class FormInfo(BaseModel):
    action: str | None = None
    fields: list[dict[str, str]] = Field(default_factory=list)
    checkboxes: list[dict[str, str | bool]] = Field(default_factory=list)


class Page(BaseModel):
    url: str
    status_code: int
    title: str = ""
    description: str = ""
    canonical: str | None = None
    lang: str = ""
    robots_meta: str = ""
    robots_meta_by_agent: dict[str, str] = Field(default_factory=dict)
    x_robots_tag: str = ""
    content_type: str = ""
    h1: list[str] = Field(default_factory=list)
    h2: list[str] = Field(default_factory=list)
    text: str = ""
    internal_links: list[str] = Field(default_factory=list)
    document_links: list[str] = Field(default_factory=list)
    document_labels: list[str] = Field(default_factory=list)
    document_link_labels: dict[str, str] = Field(default_factory=dict)
    scripts: list[str] = Field(default_factory=list)
    structured_data: list[dict | list | str] = Field(default_factory=list)
    forms: list[FormInfo] = Field(default_factory=list)
    html_bytes: int = 0
    source_sha256: str = ""


class SiteSnapshot(BaseModel):
    input_url: str
    final_url: str
    pages: list[Page] = Field(default_factory=list)
    robots_txt: str | None = None
    sitemap_found: bool | None = None
    sitemap_status: int | None = None
    sitemap_declared: list[str] = Field(default_factory=list)
    crawl_limit_reached: bool = False
    crawl_notes: list[str] = Field(default_factory=list)
    access_diagnostics: list[AccessDiagnostic] = Field(default_factory=list)
    browser_evidence: list[dict] = Field(default_factory=list)


class AuditReport(BaseModel):
    scanned_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "0.2.4"
    target: str
    agents: list[AgentName]
    pages_scanned: int
    findings: list[Finding]
    coverage: dict[str, str | int | bool] = Field(default_factory=dict)
    crawl_notes: list[str] = Field(default_factory=list)
    access_diagnostics: list[AccessDiagnostic] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
