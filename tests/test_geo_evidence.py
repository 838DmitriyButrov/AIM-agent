"""Regression checks for site-specific robots rules and JSON-LD observations."""
import pytest

from siteaudit.agents.geo import GeoAgent
from siteaudit.models import Page, SiteSnapshot


def findings(path="/article", *, robots="", structured_data=None):
    url = f"https://example.org{path}"
    page = Page(url=url, status_code=200, title="Example", description="Example",
                h1=["Example"], text="Sample content " * 20, structured_data=structured_data or [])
    snapshot = SiteSnapshot(input_url="https://example.org/", final_url=url, robots_txt=robots, pages=[page])
    return {finding.rule_id: finding for finding in GeoAgent().run(snapshot)}


@pytest.mark.parametrize(("rules", "path", "blocked"), [
    ("Disallow: /docs/*.pdf$", "/docs/report.pdf", True),
    ("Disallow: /docs/*.pdf$", "/docs/report.pdf/preview", False),
    ("Disallow: /catalog/\nAllow: /catalog/public/", "/catalog/public/product", False),
    ("Disallow: /catalog/\nAllow: /catalog/public/", "/catalog/internal", True),
    ("Disallow: /internal\n\nUser-agent: OAI-SearchBot\nDisallow: /private", "/private", True),
])
def test_geo_applies_robots_patterns_and_precedence(rules, path, blocked):
    result = findings(path, robots=f"User-agent: OAI-SearchBot\n{rules}")
    assert ("GEO-OAI-SEARCHBOT-ROBOTS" in result) == blocked
    assert "GEO-GOOGLEBOT-ROBOTS" not in result


def test_google_extended_reported_as_content_use_policy():
    result = findings(robots="User-agent: Google-Extended\nDisallow: /")
    assert not any(rule.endswith("-ROBOTS") for rule in result)
    policy = result["GEO-GOOGLE-EXTENDED-POLICY"]
    assert policy.status == "observation"
    assert policy.severity == "info"
    assert "включение страницы в Google Search" in policy.explanation


@pytest.mark.parametrize("nodes", [
    [{"@type": "Article"}],
    [[{"@type": "Article"}]],
    [{"@graph": [{"@type": "Article"}]}],
    [{"mainEntity": {"@type": ["Article", "NewsArticle"]}}],
])
def test_geo_reports_declared_types_in_supported_json_ld_shapes(nodes):
    result = findings(structured_data=nodes)["GEO-SCHEMA-TYPES"]
    assert "Article" in result.explanation
    assert "Product" not in result.explanation
    assert "FAQPage" not in result.explanation


def test_absence_of_json_ld_types_is_not_reported():
    result = findings(structured_data=[{"@context": {"price": {"@type": "Text"}}}])
    assert "GEO-SCHEMA-TYPES" not in result


def test_malformed_block_does_not_hide_other_declared_types():
    result = findings(structured_data=["INVALID_JSON_LD", {"@type": "Article"}])
    assert "GEO-SCHEMA-INVALID" in result
    assert "Article" in result["GEO-SCHEMA-TYPES"].explanation
