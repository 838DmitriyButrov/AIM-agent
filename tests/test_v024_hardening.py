"""Hardening regression suite: robots identity, auth scope, URL coverage and API guard."""
from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from siteaudit import crawler, api
from siteaudit.agents.geo import GeoAgent
from siteaudit.extract import parse_page
from siteaudit.models import SiteSnapshot


def fixture_crawler(monkeypatch, handler):
    original_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(crawler.httpx, "Client",
                        lambda **kwargs: original_client(transport=transport, **kwargs))
    monkeypatch.setattr(crawler, "validate_public_url", lambda url: url)
    return crawler.SiteCrawler(max_pages=2, delay=0)


def test_robots_own_product_token_is_honored(monkeypatch):
    requested = []
    def handler(req):
        requested.append(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: SiteAuditAgents\nDisallow: /\n\nUser-agent: *\nAllow: /")
        if req.url.path == "/sitemap.xml":
            return httpx.Response(404)
        raise AssertionError("Crawler ignored a robots disallow rule")
    snapshot = fixture_crawler(monkeypatch, handler).crawl("https://example.org/")
    assert snapshot.pages == []
    assert requested == ["/robots.txt", "/sitemap.xml"]
    assert any("Disallowed by robots.txt" in note for note in snapshot.crawl_notes)
    assert crawler.USER_AGENT.startswith("SiteAuditAgents/")


def test_scoped_auth_is_sent_only_to_approved_html_host(monkeypatch):
    monkeypatch.setenv("SITEAUDIT_AUTH", "Bearer fixture-test-key")
    monkeypatch.setenv("SITEAUDIT_AUTH_HOST", "example.org")
    auth_seen = []
    def handler(req):
        auth_seen.append((req.url.path, req.headers.get("authorization")))
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/sitemap.xml":
            return httpx.Response(404)
        return httpx.Response(200, text="<html><body>OK</body></html>", headers={"content-type": "text/html"})
    snap = fixture_crawler(monkeypatch, handler).crawl("https://example.org/")
    assert len(snap.pages) == 1
    assert auth_seen == [("/robots.txt", None), ("/sitemap.xml", None),
                         ("/", "Bearer fixture-test-key")]


def test_auth_is_not_forwarded_on_www_redirect(monkeypatch):
    monkeypatch.setenv("SITEAUDIT_AUTH", "Bearer fixture-test-key")
    monkeypatch.setenv("SITEAUDIT_AUTH_HOST", "example.org")
    seen = []
    def handler(req):
        seen.append((req.url.host, req.url.path, req.headers.get("authorization")))
        if req.url.path in {"/robots.txt", "/sitemap.xml"}:
            return httpx.Response(404)
        if req.url.host == "example.org":
            return httpx.Response(302, headers={"location": "https://www.example.org/"})
        return httpx.Response(200, text="<html><body>Welcome</body></html>",
                              headers={"content-type": "text/html"})
    snap = fixture_crawler(monkeypatch, handler).crawl("https://example.org/")
    assert len(snap.pages) == 1
    assert ("example.org", "/", "Bearer fixture-test-key") in seen
    assert ("www.example.org", "/", None) in seen


def test_auth_without_host_fails_closed(monkeypatch):
    monkeypatch.setenv("SITEAUDIT_AUTH", "Bearer fixture-test-key")
    monkeypatch.delenv("SITEAUDIT_AUTH_HOST", raising=False)
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/sitemap.xml":
            return httpx.Response(404)
        raise AssertionError("HTML should not be requested with unscoped auth")
    snap = fixture_crawler(monkeypatch, handler).crawl("https://example.org/")
    assert snap.pages == []
    assert any("SITEAUDIT_AUTH requires" in x for x in snap.crawl_notes)


def test_browser_encoding_claim_matches_available_decoders():
    assert "br" not in crawler.DEFAULT_HEADERS["Accept-Encoding"]
    assert crawler.DEFAULT_HEADERS["User-Agent"].startswith("SiteAuditAgents/")


def test_safe_query_parameters_are_kept_with_sensitive_parameters_removed():
    url = "https://example.org/catalog/?utm_source=x&page=2&sort=price&filter=smartphones&token=SECRET"
    normalized = crawler.strip_tracking(url)
    assert normalized == "https://example.org/catalog/?filter=smartphones&page=2&sort=price"
    assert "SECRET" not in normalized
    assert crawler.strip_tracking("https://example.org/p/?q=user%40example.com") == "https://example.org/p/"


def test_bot_only_noindex_is_explicitly_scoped():
    url = "https://example.org/"
    page = parse_page(url, 200, '''<html><head><title>Catalog</title>
        <meta name="googlebot" content="noindex"></head><body><h1>Catalog</h1></body></html>''')
    snap = SiteSnapshot(input_url=url, final_url=url, pages=[page],
                        robots_txt="User-agent: *\nAllow: /", sitemap_found=True)
    matches = [f for f in GeoAgent().run(snap) if f.rule_id == "GEO-NOINDEX"]
    assert len(matches) == 1
    assert "googlebot" in matches[0].explanation
    assert "всех поисковых систем" in matches[0].explanation


def test_busy_private_api_returns_429_without_running_crawler(monkeypatch):
    monkeypatch.setenv("AUDIT_TOKEN", "x" * 40)
    monkeypatch.setenv("AUDIT_ALLOWED_HOSTS", "example.org")
    class Busy:
        def acquire(self, blocking=False):
            return False
        def release(self):
            raise AssertionError("release must not be called")
    monkeypatch.setattr(api, "SCAN_SEMAPHORE", Busy())
    monkeypatch.setattr(api, "run_audit", lambda *args, **kwargs:
                        (_ for _ in ()).throw(AssertionError("crawler must not run")))
    response = TestClient(api.app).post("/scan", json={"url": "https://example.org/"},
                                        headers={"Authorization": "Bearer " + "x" * 40})
    assert response.status_code == 429


def test_invalid_port_is_rejected_without_internal_error(monkeypatch):
    monkeypatch.setenv("AUDIT_TOKEN", "x" * 40)
    monkeypatch.setenv("AUDIT_ALLOWED_HOSTS", "example.org")
    response = TestClient(api.app).post("/scan", json={"url": "https://example.org:abc/"},
                                        headers={"Authorization": "Bearer " + "x" * 40})
    assert response.status_code == 403
