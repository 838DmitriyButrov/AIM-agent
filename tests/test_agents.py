import json
import pytest
from siteaudit.extract import parse_page
from siteaudit.models import SiteSnapshot, AuditReport
from siteaudit.agents.legal import LegalAgent, rules_by_id
from siteaudit.agents.geo import GeoAgent
from siteaudit.crawler import validate_public_url, UnsafeTarget
from siteaudit.report import to_markdown
from siteaudit.orchestrator import run_audit

URL = "https://example.org/"


def snap(html: str, robots: str = "User-agent: *\nAllow: /") -> SiteSnapshot:
    page = parse_page(URL, 200, html)
    return SiteSnapshot(input_url=URL, final_url=URL, pages=[page], robots_txt=robots, sitemap_found=True)


def test_legal_consent_and_policy_observations():
    s = snap('''<html lang="ru"><head><title>Оставить заявку</title></head>
    <body><form><input type="email" name="email" required>
    <label><input type="checkbox" checked>Согласен с обработкой персональных данных и условиями оферты</label>
    </form></body></html>''')
    found = LegalAgent().run(s)
    ids = {f.rule_id for f in found}
    assert "LEGAL-PD-POLICY" in ids
    assert "LEGAL-PD-CONSENT" in ids
    assert all(f.needs_human_review for f in found)
    assert all(f.status != "passed" for f in found)


def test_legal_policy_present_not_false_positive():
    s = snap('''<html lang="ru"><head><title>Сервис</title></head><body>
    <a href="/privacy-policy">Политика обработки персональных данных</a>
    <form><input type="email" name="email"><label><input type="checkbox">Я прочитал политику</label></form>
    </body></html>''')
    found = LegalAgent().run(s)
    assert not any(f.rule_id == "LEGAL-PD-POLICY" and f.status in {"potential_risk", "needs_review"} for f in found)
    assert any(f.rule_id == "LEGAL-PD-POLICY" and f.status == "not_tested" for f in found)
    assert not any(f.rule_id == "LEGAL-PD-CONSENT" for f in found)


def test_geo_real_findings_and_no_fake_ai_visibility():
    s = snap('''<html lang="ru"><head><meta name="robots" content="noindex">
    <script type="application/ld+json">{INVALID}</script></head>
    <body><main>Малая страница</main></body></html>''')
    found = GeoAgent().run(s)
    by_id = {f.rule_id: f for f in found}
    assert "GEO-NOINDEX" in by_id
    assert "GEO-TITLE" in by_id
    assert "GEO-SCHEMA-INVALID" in by_id
    assert by_id["GEO-AI-VISIBILITY"].status == "not_tested"


def test_parser_does_not_capture_form_values():
    p = parse_page(URL, 200, '''<html><form><input type="email" name="email" value="private@example.com">
        <input type="password" name="password" value="secret"></form></html>''')
    assert len(p.forms) == 1
    assert "private@example.com" not in p.model_dump_json()
    assert "secret" not in p.model_dump_json()


def test_urls_reject_private_network_and_credentials():
    for addr in ["http://127.0.0.1/", "http://10.0.0.1/", "http://169.254.169.254/", "http://localhost/",
                 "ftp://example.org/", "http://user:pass@example.org/", "https://example.org:8080/"]:
        with pytest.raises(UnsafeTarget):
            validate_public_url(addr)


def test_registry_has_sources_and_no_invented_cases():
    rules = rules_by_id()
    assert len(rules) >= 8
    assert all(r.get("source", "").startswith("https://") for r in rules.values())
    assert all(r.get("case_law") == [] for r in rules.values())  # not yet investigated, explicit gap


def test_report_formats():
    findings = LegalAgent().run(snap("<html><head><title>Home</title></head><body>OK</body></html>"))
    r = AuditReport(target=URL, agents=["legal"], pages_scanned=1, findings=findings)
    assert json.loads(r.model_dump_json())["pages_scanned"] == 1
    assert "## Находки" in to_markdown(r)
    assert "LEGAL" in to_markdown(r)


def test_ux_not_silently_executed():
    with pytest.raises(ValueError, match="only agents"):
        run_audit(URL, ["ux"])


def test_no_access_means_no_compliance_claim():
    s = SiteSnapshot(input_url=URL, final_url=URL)
    assert LegalAgent().run(s)[0].status == "not_tested"
    assert GeoAgent().run(s)[0].status == "not_tested"
