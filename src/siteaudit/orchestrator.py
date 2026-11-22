"""Single scan orchestrator; agents share the same crawl and immutable evidence."""
from __future__ import annotations
from urllib.parse import urlparse
from .agents.geo import GeoAgent
from .agents.legal import LegalAgent
from .crawler import SiteCrawler, DNSResolutionError
from .models import AuditReport
from .search_results import SearchSnapshot, compare_search

DISCLAIMER = [
    "Результаты — предварительная техническая диагностика, а не юридическое заключение или сертификат соответствия.",
    "Не обнаружено != отсутствует: обход ограничен числом страниц, robots.txt, HTML и доступным пользователю контентом.",
    "Признак риска не равен установленному нарушению. Для юридической квалификации нужны условия применимости нормы и экспертная проверка.",
    "GEO-готовность не доказывает попадание в ответы ИИ; достоверная видимость требует данных поисковых платформ.",
    "Не тестируются внутренние процессы и закрытые области; отсутствие находок не означает соответствие.",
    "DNS URL-валидация не предотвращает DNS rebinding: публичный сервис требует отдельной сетевой изоляции.",
]


def run_audit(url: str, agents: list[str] | None = None, max_pages: int = 12,
              with_browser: bool = False, with_ai: bool = False, queries: list[str] | None = None,
              search_snapshots: list[SearchSnapshot] | None = None) -> AuditReport:
    selected = list(dict.fromkeys(agents or ["legal", "geo"]))
    if any(agent not in {"legal", "geo"} for agent in selected):
        raise ValueError("Phase one supports only agents: legal, geo. UX is reserved for phase two.")
    if search_snapshots and "geo" not in selected:
        raise ValueError("Для сравнения с выдачей нужен агент GEO.")
    try:
        crawler = SiteCrawler(max_pages=max_pages)
        if search_snapshots:
            target_host = (urlparse(url).hostname or "").lower()
            priority_urls = list(dict.fromkeys(
                str(result.url) for source in search_snapshots for result in source.results
                if result.url.host == target_host
            ))
            snapshot = crawler.crawl(url, priority_urls=priority_urls)
        else:
            snapshot = crawler.crawl(url)
    except DNSResolutionError as exc:
        # Environmental failure is NOT a website flaw. Do not run LEGAL/GEO engines
        # on an empty snapshot and imply compliance or the absence of findings.
        return AuditReport(
            target=url, agents=selected, pages_scanned=0, findings=[],
            coverage={"scan_status": "blocked_network", "error_code": exc.code,
                      "sampled_pages": 0, "confirmed_ai_search_visibility": False,
                      "verified_legal_compliance": False},
            crawl_notes=[f"{exc.code}: {exc}. Check DNS/network access with `siteaudit doctor`."],
            methods=["Network/DNS preflight only; no site content was retrieved"],
            disclaimers=DISCLAIMER,
        )
    if not snapshot.pages and any(note.startswith(("DNS_TEMPORARY:", "DNS_NOT_FOUND:", "DNS_ERROR:")) for note in snapshot.crawl_notes):
        return AuditReport(
            target=url, agents=selected, pages_scanned=0, findings=[],
            coverage={"scan_status": "blocked_network", "error_code": "DNS_DURING_CRAWL",
                      "sampled_pages": 0, "confirmed_ai_search_visibility": False,
                      "verified_legal_compliance": False},
            crawl_notes=snapshot.crawl_notes,
            methods=["Network/DNS preflight only; robots.txt could not be retrieved"],
            disclaimers=DISCLAIMER,
        )
    # HTTP access refusals are coverage limitations, never SEO/LEGAL defects.
    if not snapshot.pages:
        direct_access = [d for d in snapshot.access_diagnostics if d.phase in {"robots", "page"}]
        if direct_access:
            first = direct_access[0]
            status = "rate_limited" if first.status_code == 429 else "blocked_http"
        elif any(("robots.txt" in note and "stopped conservatively" in note) or note.startswith("Disallowed by robots.txt:") for note in snapshot.crawl_notes):
            first = None
            status = "blocked_robots"
        else:
            first = None
            status = "no_pages"
        return AuditReport(
            target=url, agents=selected, pages_scanned=0, findings=[],
            coverage={"scan_status": status, "sampled_pages": 0,
                      "max_pages_requested": max_pages,
                      "sitemap_declarations": len(snapshot.sitemap_declared),
                      "sitemap_xml_detected": snapshot.sitemap_found if snapshot.sitemap_found is not None else "unknown",
                      "sitemap_http_status": snapshot.sitemap_status if snapshot.sitemap_status is not None else "unknown",
                      "http_status": first.status_code if first else 0,
                      "access_restrictions_detected": len(snapshot.access_diagnostics),
                      "confirmed_ai_search_visibility": False,
                      "verified_legal_compliance": False},
            crawl_notes=snapshot.crawl_notes,
            access_diagnostics=snapshot.access_diagnostics,
            methods=["Read-only same-site HTTP crawl; no auditable HTML returned"],
            disclaimers=DISCLAIMER,
        )
    methods = ["Read-only same-site HTTP crawl", "Rule-based DOM analysis", "Versioned legal rule registry"]
    if with_browser and snapshot.pages:
        try:
            from .browser import passive_browser_probe
            snapshot.browser_evidence.append(passive_browser_probe(snapshot.pages[0].url))
            methods.append("Opt-in Playwright first-page probe; no form submission")
        except Exception as exc:
            snapshot.crawl_notes.append(f"Optional browser probe failed: {type(exc).__name__}: {str(exc)[:150]}")
    findings = []
    for name in selected:
        findings.extend((LegalAgent() if name == "legal" else GeoAgent(queries=None if search_snapshots else queries)).run(snapshot))
    if with_browser and snapshot.browser_evidence and "legal" in selected:
        from .models import Finding, Evidence
        signal = snapshot.browser_evidence[0]
        findings.append(Finding(id="LEGAL-COOKIE-OBS-1", agent="legal", rule_id="COOKIE-OBSERVATION",
            title="Пассивное наблюдение сетевой активности и cookies до взаимодействия",
            explanation=f"Домены запросов: {', '.join(signal.get('completed_request_domains', [])[:25])}. Cookies: {len(signal['cookies_before_interaction'])}. Наличие cookies не означает автоматического нарушения.",
            severity="info", status="observation", confidence="high", action="Сопоставить цели, состав данных и правовые основания обработки; при необходимости изучить все сценарии согласия.",
            evidence=[Evidence(page=signal['url'], kind="browser", detail="Cookie names and completed request domains recorded; no cookie values stored")],
            needs_human_review=True))
    if with_ai and snapshot.pages:
        from .ai import ai_review
        findings.extend(ai_review(snapshot, selected, queries or []))
        methods.append("Opt-in external LLM review of selected PUBLIC page excerpts")
    search_coverage = {}
    if search_snapshots:
        search_findings, search_coverage = compare_search(snapshot, search_snapshots)
        findings.extend(search_findings)
        methods.append("Organic search snapshot matched to the same URL in the crawled sample")
    coverage = {
        **search_coverage,
        'scan_status': 'completed_sample_with_restrictions' if snapshot.access_diagnostics else 'completed_sample',
        'sampled_pages': len(snapshot.pages),
        'access_restrictions_detected': len(snapshot.access_diagnostics),
        'max_pages_requested': max_pages,
        'crawl_limit_reached': snapshot.crawl_limit_reached,
        'browser_pages_probed': len(snapshot.browser_evidence),
        'confirmed_ai_search_visibility': False,
        'verified_legal_compliance': False,
        'sitemap_declarations': len(snapshot.sitemap_declared),
    }
    return AuditReport(target=url, agents=selected, pages_scanned=len(snapshot.pages), findings=findings,
                       coverage=coverage, crawl_notes=snapshot.crawl_notes,
                       access_diagnostics=snapshot.access_diagnostics,
                       methods=methods, disclaimers=DISCLAIMER)
