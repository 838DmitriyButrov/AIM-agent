import json
from types import SimpleNamespace

import pytest

from siteaudit import benchmark, orchestrator
from siteaudit.models import AccessDiagnostic, SiteSnapshot


@pytest.mark.parametrize(
    ("args", "sites", "limit"),
    [([], list(benchmark.SITES), 3), (["--site", "metro", "--max-pages", "12"], ["metro"], 12)],
)
def test_benchmark_budget(monkeypatch, capsys, args, sites, limit):
    calls = []

    def audit(url, *, agents, max_pages):
        calls.append((url, agents, max_pages))
        return SimpleNamespace(
            findings=[], version="test", scanned_at_utc=benchmark.datetime.now(benchmark.timezone.utc),
            pages_scanned=0, coverage={}, crawl_notes=[], access_diagnostics=[], methods=[],
        )

    monkeypatch.setattr(benchmark, "run_audit", audit)
    assert benchmark.main(args) == 0
    lines = capsys.readouterr().out.splitlines()
    start = json.loads(lines[0].split(" ", 1)[1])
    assert start["sites"] == sites
    assert start["max_pages_per_site"] == limit
    assert calls == [(benchmark.SITES[site], ["legal", "geo"], limit) for site in sites]
    assert sum(line.startswith("SCAN_RESULT ") for line in lines) == len(sites)


def test_benchmark_rejects_invalid_budget(monkeypatch):
    monkeypatch.setattr(benchmark, "run_audit", lambda *args: pytest.fail("Must not contact sites"))
    with pytest.raises(SystemExit) as error:
        benchmark.main(["--max-pages", "51"])
    assert error.value.code == 2


@pytest.mark.parametrize("sitemap_status", [200, None])
def test_blocked_html_keeps_sitemap_metadata(monkeypatch, sitemap_status):
    url = "https://example.com/"
    snapshot = SiteSnapshot(
        input_url=url, final_url=url,
        sitemap_declared=[url + "sitemap.xml"],
        sitemap_found=True if sitemap_status else None,
        sitemap_status=sitemap_status,
        access_diagnostics=[AccessDiagnostic(
            phase="page", url=url, status_code=401, response_class="authentication_or_policy",
        )],
    )
    monkeypatch.setattr(orchestrator.SiteCrawler, "crawl", lambda self, target: snapshot)
    report = orchestrator.run_audit(url, with_browser=True)
    assert report.pages_scanned == 0
    assert report.findings == []
    assert report.coverage["scan_status"] == "blocked_http"
    assert report.coverage["http_status"] == 401
    assert report.coverage["sitemap_declarations"] == 1
    assert report.coverage["sitemap_xml_detected"] == (True if sitemap_status else "unknown")
    assert report.coverage["sitemap_http_status"] == (200 if sitemap_status else "unknown")
