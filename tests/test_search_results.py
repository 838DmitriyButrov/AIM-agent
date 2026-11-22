import base64
import json

import httpx

from siteaudit import crawler, orchestrator
from siteaudit.cli import main
from siteaudit.models import Page, SiteSnapshot
from siteaudit.report import to_markdown
from siteaudit.search_results import SearchSnapshot, compare_search, yandex_snapshots


def search_source():
    return SearchSnapshot.model_validate({
        "engine": "Google", "query": "купить ковёр", "region": "Москва",
        "source": "Ручной снимок Google Search", "observed_at": "2026-11-22T12:00:00+03:00",
        "results": [
            {"url": "https://example.org/rug/", "position": 3, "title": "Ковры для гостиной", "snippet": "Ковры из шерсти"},
            {"url": "https://other.example/rug/", "position": 4, "title": "Другой сайт"},
        ],
    })


def test_compare_keeps_query_and_actual_values_and_does_not_claim_rank_impact():
    url = "https://example.org/rug/"
    page = Page(url=url, status_code=200, title="Каталог ковров", description="Ковры из шерсти")
    site = SiteSnapshot(input_url=url, final_url=url, pages=[page])
    records, coverage = compare_search(site, [search_source()])
    assert coverage == {"serp_queries_checked": 1, "serp_urls_matched": 1, "serp_fields_compared": 2}
    assert [record.rule_id for record in records] == ["GEO-SERP-TITLE", "GEO-SERP-MATCH"]
    assert records[0].status == "needs_review"
    assert all(text in records[0].explanation for text in ("купить ковёр", "Москва", "Каталог ковров", "Ковры для гостиной"))


def test_different_query_url_does_not_match():
    url = "https://example.org/rug/?color=green"
    site = SiteSnapshot(input_url=url, final_url=url, pages=[Page(url=url, status_code=200, title="Green")])
    records, coverage = compare_search(site, [search_source()])
    assert coverage["serp_fields_compared"] == 0
    assert records[0].status == "not_tested"


def test_cli_compares_file_through_real_crawler(monkeypatch, tmp_path):
    original_client = httpx.Client
    requested = []

    def respond(request):
        path = request.url.path
        requested.append(path)
        assert request.url.host == "example.org"
        if path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if path == "/sitemap.xml":
            return httpx.Response(404)
        if path == "/":
            return httpx.Response(200, text='<html><title>Главная</title><a href="/unrelated/">Другое</a></html>',
                                  headers={"Content-Type": "text/html"})
        assert path == "/rug/"
        return httpx.Response(200, text='<html><title>Старый заголовок</title><h1>Ковры</h1></html>',
                              headers={"Content-Type": "text/html"})

    monkeypatch.setattr(crawler, "validate_public_url", lambda url: url)
    monkeypatch.setattr(crawler.time, "sleep", lambda value: None)
    monkeypatch.setattr(crawler.httpx, "Client",
                        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    snapshots = tmp_path / "search.json"
    snapshots.write_text("[" + search_source().model_dump_json() + "]", encoding="utf-8")
    output = tmp_path / "audit"
    assert main(["scan", "https://example.org/", "--agent", "geo", "--max-pages", "2",
                 "--serp-file", str(snapshots), "--out", str(output)]) == 0
    assert requested == ["/robots.txt", "/sitemap.xml", "/", "/rug/"]
    report = output.with_suffix(".md").read_text(encoding="utf-8")
    assert all(text in report for text in ("Что видно в поисковой выдаче", "Старый заголовок", "Ковры для гостиной"))


def test_yandex_api_extracts_title_and_passages_with_context(monkeypatch):
    original_client = httpx.Client
    xml = b"<yandexsearch><response><results><grouping><group><doc><url>https://example.org/</url><title>A <hlword>rug</hlword></title><passages><passage>Wool <hlword>rug</hlword></passage></passages></doc></group></grouping></results></response></yandexsearch>"

    def respond(request):
        assert str(request.url) == "https://searchapi.api.cloud.yandex.net/v2/web/search"
        assert request.headers["Authorization"] == "Api-Key fake-test-key"
        body = json.loads(request.content)
        assert body["region"] == "213"
        assert body["query"]["queryText"] == "купить ковёр"
        return httpx.Response(200, json={"rawData": base64.b64encode(xml).decode()})

    monkeypatch.setenv("YANDEX_SEARCH_API_KEY", "fake-test-key")
    monkeypatch.setenv("YANDEX_SEARCH_FOLDER_ID", "fake-test-folder")
    monkeypatch.setattr(httpx, "Client",
                        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    result = yandex_snapshots(["купить ковёр"], "213")[0]
    assert result.results[0].title == "A rug"
    assert result.results[0].snippet == "Wool rug"
    assert result.source.startswith("Яндекс Search API")


def test_crawl_refusal_does_not_check_priority_urls(monkeypatch):
    original_client = httpx.Client

    def respond(request):
        if request.url.path in {"/robots.txt", "/sitemap.xml"}:
            return httpx.Response(404)
        assert request.url.path == "/"
        return httpx.Response(401)

    monkeypatch.setattr(crawler, "validate_public_url", lambda url: url)
    monkeypatch.setattr(crawler.httpx, "Client",
                        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    report = orchestrator.run_audit("https://example.org/", agents=["geo"], search_snapshots=[search_source()])
    assert report.coverage["scan_status"] == "blocked_http"
    assert report.findings == []
    assert "Выдача не проверена" in to_markdown(report)


def test_visible_prefix_with_ellipsis_is_labeled_as_truncation():
    url = "https://example.org/rug/"
    page = Page(url=url, status_code=200, title="Ковры для гостиной с доставкой")
    site = SiteSnapshot(input_url=url, final_url=url, pages=[page])
    source = search_source()
    source.results[0].title = "Ковры для гостиной ..."
    source.results[0].snippet = ""
    results, _ = compare_search(site, [source])
    assert results[0].rule_id == "GEO-SERP-TRUNCATED"
    assert "показан сокращённо" in results[0].title
