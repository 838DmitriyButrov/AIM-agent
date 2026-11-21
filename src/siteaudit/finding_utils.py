"""Deterministic IDs and conservative evidence assembly."""
from __future__ import annotations
import hashlib
from .models import Evidence, Finding, Page


def issue_id(agent: str, rule: str, page: str, context: str = "") -> str:
    stable_key = f"{agent}|{rule}|{page.rstrip('/')}|{context}"
    return f"{rule}-{hashlib.sha256(stable_key.encode()).hexdigest()[:12]}"


def evidence_from_page(page: Page, kind: str, detail: str, selector: str | None = None) -> Evidence:
    return Evidence(page=page.url, kind=kind, detail=detail[:600], selector=selector,
                    source_sha256=page.source_sha256 or None)
