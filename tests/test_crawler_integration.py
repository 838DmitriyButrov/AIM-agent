"""No external network: integrate bounded crawler with httpx MockTransport."""
import httpx
from siteaudit import crawler


def mocked_crawler(monkeypatch, handler, max_pages=5):
    original = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(crawler.httpx, 'Client', lambda **kwargs: original(transport=transport, **kwargs))
    monkeypatch.setattr(crawler, 'validate_public_url', lambda url: url if url.startswith('https://example.org/') else (_ for _ in ()).throw(crawler.UnsafeTarget('outside fixture')))
    return crawler.SiteCrawler(max_pages=max_pages, delay=0)


def test_crawler_is_bounded_and_skips_robots_and_destructive_paths(monkeypatch):
    requests = []
    def handler(req):
        requests.append(req.url.path)
        path = req.url.path
        if path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /secret\nSitemap: https://example.org/custom.xml')
        if path == '/sitemap.xml':
            return httpx.Response(200, text='<html>not sitemap</html>')
        if path == '/':
            return httpx.Response(200, text='<html><a href="/page">Page</a><a href="/secret">Secret</a><a href="/logout">Logout</a></html>', headers={'Content-Type': 'text/html'})
        if path == '/page':
            return httpx.Response(200, text='<html><head><title>Page</title></head><body>Hello</body></html>', headers={'Content-Type': 'text/html', 'X-Robots-Tag': 'noindex'})
        raise AssertionError(f'Unexpected GET to {path}')
    snap = mocked_crawler(monkeypatch, handler).crawl('https://example.org/')
    assert len(snap.pages) == 2
    assert snap.pages[1].x_robots_tag == 'noindex'
    assert '/secret' not in requests
    assert '/logout' not in requests
    assert snap.sitemap_found is False
    assert snap.sitemap_declared == ['https://example.org/custom.xml']
    assert any('Disallowed' in n for n in snap.crawl_notes)


def test_crawler_valid_xml_sitemap(monkeypatch):
    def handler(req):
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        if req.url.path == '/sitemap.xml':
            return httpx.Response(200, text='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>')
        return httpx.Response(200, text='<html><title>Okay</title></html>', headers={'Content-Type': 'text/html'})
    snap = mocked_crawler(monkeypatch, handler).crawl('https://example.org/')
    assert snap.sitemap_found is True
    assert len(snap.pages) == 1


def test_robots_unavailable_fails_closed(monkeypatch):
    def handler(req):
        assert req.url.path == '/robots.txt'
        return httpx.Response(503)
    snap = mocked_crawler(monkeypatch, handler).crawl('https://example.org/')
    assert not snap.pages
    assert 'stopped conservatively' in snap.crawl_notes[0]


def test_redirect_to_out_of_scope_host_not_fetched(monkeypatch):
    paths = []
    def handler(req):
        paths.append(str(req.url))
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        if req.url.path == '/sitemap.xml':
            return httpx.Response(404)
        return httpx.Response(302, headers={'Location': 'https://internal.example.net/secret'})
    snap = mocked_crawler(monkeypatch, handler).crawl('https://example.org/')
    assert not snap.pages
    assert not any('internal.example.net' in url for url in paths)
