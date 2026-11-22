"""Regression checks for HTTP access diagnostics and fail-closed private API."""
from __future__ import annotations
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from siteaudit import crawler, orchestrator, api
from siteaudit.report import to_markdown
from siteaudit.models import AuditReport


def run_mock(monkeypatch, handler):
    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(crawler.httpx, "Client",
                        lambda **kwargs: real_client(transport=transport, **kwargs))
    monkeypatch.setattr(crawler, "validate_public_url", lambda url: url)
    monkeypatch.setattr(orchestrator, "SiteCrawler",
                        lambda **kwargs: crawler.SiteCrawler(delay=0, **kwargs))
    return orchestrator.run_audit("https://example.org/", max_pages=3)


def responder(status, headers=None, body="Access denied"):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(404)
        return httpx.Response(status, text=body, headers=headers or {})
    return handler


def test_401_classified_as_blocked_audit_not_seo_finding(monkeypatch):
    report = run_mock(monkeypatch, responder(401, {
        "WWW-Authenticate": "Basic realm=private-portal",
        "Set-Cookie": "SECRET_SESSION=do-not-save",
        "Server": "cloudflare",
        "CF-Ray": "do-not-save-identifiers",
        "Content-Type": "text/html; charset=utf-8",
    }, "<html>Checking your browser: captcha. SecretLogin=123</html>"))
    assert report.pages_scanned == 0
    assert report.findings == []
    assert report.coverage["scan_status"] == "blocked_http"
    assert report.coverage["http_status"] == 401
    d = report.access_diagnostics[0]
    assert d.phase == "page"
    assert d.auth_schemes == ["basic"]
    assert d.server_hint == "cloudflare"
    assert d.has_cdn_request_id is True
    assert d.challenge_indicators == ["captcha", "browser_challenge"]
    output = report.model_dump_json() + to_markdown(report)
    assert "SECRET_SESSION" not in output
    assert "SecretLogin" not in output
    assert "do-not-save" not in output
    assert "realm=private-portal" not in output
    assert "не выполнен" in output


@pytest.mark.parametrize(("code", "expected"), [(403, "blocked_http"), (429, "rate_limited")])
def test_http_refusal_never_becomes_a_site_finding(monkeypatch, code, expected):
    report = run_mock(monkeypatch, responder(code))
    assert report.coverage["scan_status"] == expected
    assert report.findings == []
    assert report.access_diagnostics[0].status_code == code


def test_robots_http_403_fails_closed(monkeypatch):
    def handler(request):
        assert request.url.path == "/robots.txt"
        return httpx.Response(403, text="Access denied", headers={"server": "nginx"})
    report = run_mock(monkeypatch, handler)
    assert report.coverage["scan_status"] == "blocked_http"
    assert report.access_diagnostics[0].phase == "robots"
    assert report.findings == []


def test_partial_crawl_retains_restrictions_but_not_as_seo_finding(monkeypatch):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/sitemap.xml":
            return httpx.Response(404)
        if request.url.path == "/":
            return httpx.Response(200, text='<html><head><title>Page</title></head><body><h1>Hi</h1><a href="/private">Private</a></body></html>', headers={"content-type":"text/html"})
        if request.url.path == "/private":
            return httpx.Response(403, text="Access denied", headers={"content-type":"text/html"})
        raise AssertionError(str(request.url))
    report = run_mock(monkeypatch, handler)
    assert report.pages_scanned == 1
    assert report.coverage["scan_status"] == "completed_sample_with_restrictions"
    assert report.coverage["access_restrictions_detected"] == 1
    assert report.access_diagnostics[0].url == "https://example.org/private"
    assert not any(f.rule_id == "GEO-CRAWL" for f in report.findings)


def test_http_500_without_pages_does_not_invent_findings(monkeypatch):
    report = run_mock(monkeypatch, responder(500))
    assert report.coverage["scan_status"] == "no_pages"
    assert report.findings == []


def test_api_fails_closed_without_explicit_configuration(monkeypatch):
    monkeypatch.delenv("AUDIT_TOKEN", raising=False)
    monkeypatch.delenv("AUDIT_ALLOWED_HOSTS", raising=False)
    response = TestClient(api.app).post("/scan", json={"url": "https://example.org/"})
    assert response.status_code == 503


def test_api_requires_token_and_allowlisted_https_host(monkeypatch):
    monkeypatch.setenv("AUDIT_TOKEN", "a" * 40)
    monkeypatch.setenv("AUDIT_ALLOWED_HOSTS", "example.org")
    client = TestClient(api.app)
    unauth = client.post("/scan", json={"url":"https://example.org/"})
    assert unauth.status_code == 401
    headers = {"Authorization":"Bearer " + "a" * 40}
    assert client.post("/scan", json={"url":"https://different.org/"}, headers=headers).status_code == 403
    assert client.post("/scan", json={"url":"http://example.org/"}, headers=headers).status_code == 403
    monkeypatch.setattr(api, "run_audit", lambda *args, **kwargs:
                        AuditReport(target="https://example.org/", agents=["geo"],
                                    pages_scanned=0, findings=[], coverage={"scan_status":"no_pages"}))
    allowed = client.post("/scan", json={"url":"https://example.org/"}, headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()["coverage"]["scan_status"] == "no_pages"


def test_http_access_helper_keeps_query_and_header_secrets_out():
    diagnostic = crawler.diagnose_http_access("page","https://example.org/?token=secret",
                                             401,"unauthorized", {
                                                 "www-authenticate":"Bearer realm=sensitive",
                                                 "set-cookie":"token=secret",
                                                 "content-type":"text/html"})
    assert diagnostic.url == "https://example.org/"
    dump = diagnostic.model_dump_json()
    assert "sensitive" not in dump
    assert "secret" not in dump
    assert diagnostic.auth_schemes == ["bearer"]


def test_browser_policy_blocks_external_hosts_methods_and_action_paths(monkeypatch):
    from siteaudit import browser
    monkeypatch.setattr(browser, "validate_public_url", lambda url: url)
    base = "https://example.org/"
    assert browser.allowed_passive_request("https://example.org/page", "GET", base)
    assert browser.allowed_passive_request("https://www.example.org/page", "GET", base)
    assert not browser.allowed_passive_request("http://example.org/page", "GET", base)
    assert not browser.allowed_passive_request("https://external.example/page", "GET", base)
    assert not browser.allowed_passive_request("https://example.org/page", "POST", base)
    assert not browser.allowed_passive_request("https://example.org/logout", "GET", base)


def test_geo_distinguishes_browser_rendered_h1():
    from siteaudit.agents.geo import GeoAgent
    from siteaudit.models import Page, SiteSnapshot
    page = Page(url="https://example.org/", status_code=200,
                title="Example", description="An example", h1=[],
                text="A public description of this site with useful text.", scripts=["main.js"])
    snapshot = SiteSnapshot(input_url=page.url, final_url=page.url, pages=[page],
                            robots_txt="User-agent: *\\nAllow: /",
                            browser_evidence=[{"url": page.url, "rendered_h1_count": 1,
                                               "rendered_text_chars": 500,
                                               "rendered_h1_text": ["Example"]}])
    findings = GeoAgent().run(snapshot)
    assert any(f.rule_id == "GEO-H1-JS" for f in findings)
    assert not any(f.rule_id == "GEO-H1" for f in findings)


def test_crawler_applies_robots_wildcards_and_more_specific_allow(monkeypatch):
    requested = []

    def handler(request):
        path = request.url.path
        requested.append(path)
        if path == "/robots.txt":
            return httpx.Response(200, text=(
                "User-agent: SiteAuditAgents\n"
                "Disallow: /catalog/*/index$\n"
                "Allow: /catalog/public/index$\n"
            ))
        if path == "/sitemap.xml":
            return httpx.Response(404)
        if path == "/":
            return httpx.Response(200, text=(
                '<html><body><a href="/catalog/private/index">Private</a>'
                '<a href="/catalog/public/index">Public</a></body></html>'
            ), headers={"content-type": "text/html"})
        assert path == "/catalog/public/index"
        return httpx.Response(200, text="<html><body>Public</body></html>",
                              headers={"content-type": "text/html"})

    report = run_mock(monkeypatch, handler)
    assert report.pages_scanned == 2
    assert "/catalog/private/index" not in requested
    assert "/catalog/public/index" in requested
