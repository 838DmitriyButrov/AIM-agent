"""Adversarial acceptance cases based on official search/legal guidance.

The fixtures assert the *kind* of claim: observation vs expert review vs not-tested.
They do not assert final legal violations or AI rankings.
"""
from siteaudit.extract import parse_page
from siteaudit.models import SiteSnapshot
from siteaudit.agents.legal import LegalAgent
from siteaudit.agents.geo import GeoAgent
from siteaudit.crawler import SiteCrawler, strip_tracking, BLOCKED_GET_PATHS

URL = "https://example.org/"


def snapshot(html: str, **kwargs):
    page = parse_page(URL, 200, html, kwargs.pop("headers", None))
    return SiteSnapshot(input_url=URL, final_url=URL, pages=[page], robots_txt=kwargs.pop("robots_txt", "User-agent: *\nAllow: /"),
                        sitemap_found=kwargs.pop("sitemap_found", True), **kwargs)


def issues(records, rid):
    return [f for f in records if f.rule_id == rid]


def test_html_policy_link_by_label_without_privacy_slug():
    snap = snapshot("""<html><a href='/doc/42'>Политика обработки персональных данных</a>
    <form><input type='email' name='email'></form></html>""")
    out = LegalAgent().run(snap)
    policy = issues(out, "LEGAL-PD-POLICY")
    assert len(policy) == 1 and policy[0].status == "not_tested"
    assert "не проверен" in policy[0].title


def test_crawler_sample_policy_absence_is_not_certified_violation():
    snap = snapshot("<html><form><input type='tel' name='phone'></form></html>", crawl_limit_reached=True)
    out = LegalAgent().run(snap)
    policy = issues(out, "LEGAL-PD-POLICY")
    assert policy and all(f.status == "needs_review" for f in policy)
    assert all(f.needs_human_review for f in policy)


def test_no_personal_forms_no_spurious_legal_tasks():
    snap = snapshot("<html><head><title>Привет</title></head><body><p>Наша компания</p></body></html>")
    assert LegalAgent().run(snap) == []


def test_separate_consents_are_not_flagged_as_combined():
    snap = snapshot("""<html><form><input type='email' name='email'>
    <label><input type='checkbox'>Согласие на обработку персональных данных</label>
    <label><input type='checkbox'>Согласен с условиями оферты</label>
    <a href='/privacy'>Политика обработки персональных данных</a></form></html>""")
    out = LegalAgent().run(snap)
    assert not issues(out, "LEGAL-PD-CONSENT")


def test_combined_consent_and_prechecked_two_distinct_signals_with_direct_evidence():
    snap = snapshot("""<html><form><input type='email' name='email'>
    <label><input type='checkbox' checked>Согласен на обработку персональных данных и с условиями оферты</label>
    </form></html>""")
    out = issues(LegalAgent().run(snap), "LEGAL-PD-CONSENT")
    assert len(out) == 2
    assert any(f.evidence_level == "direct" for f in out)
    assert all(f.references and f.applicability == "conditional" for f in out)


def test_direct_noindex_in_http_header_is_observed():
    snap = snapshot('<html><head><title>Home</title></head><body><h1>Home</h1></body></html>',
                    headers={"X-Robots-Tag": "noindex, nosnippet"})
    out = GeoAgent().run(snap)
    assert issues(out, "GEO-NOINDEX")
    assert issues(out, "GEO-SNIPPET-RESTRICTION")
    assert issues(out, "GEO-NOINDEX")[0].evidence[0].source_sha256


def test_search_bot_specific_meta_directive():
    snap = snapshot('<html><head><title>Demo</title><meta name="googlebot" content="noindex"></head><body></body></html>')
    assert issues(GeoAgent().run(snap), "GEO-NOINDEX")


def test_googlebot_blocked_not_assumed_deindexed():
    snap = snapshot('<html><head><title>Demo</title></head><body><h1>Demo</h1></body></html>',
        robots_txt="User-agent: Googlebot\nDisallow: /\nUser-agent: SiteAuditAgents\nAllow: /\nUser-agent: *\nAllow: /")
    out = GeoAgent().run(snap)
    blocked = issues(out, "GEO-GOOGLEBOT-ROBOTS")
    assert blocked and blocked[0].status == "observation"
    assert "не гарантирует" in blocked[0].explanation


def test_custom_sitemap_declaration_does_not_trigger_missing_sitemap():
    snap = snapshot('<html><head><title>Demo</title></head><body></body></html>',
        sitemap_found=False, sitemap_declared=["https://example.org/maps/content.xml"])
    out = GeoAgent().run(snap)
    assert not issues(out, "GEO-SITEMAP")
    assert issues(out, "GEO-SITEMAP-UNVERIFIED")[0].status == "not_tested"


def test_no_schema_not_counted_as_geo_issue():
    snap = snapshot('<html><head><title>Demo</title></head><body><h1>Example</h1></body></html>')
    assert not issues(GeoAgent().run(snap), "GEO-SCHEMA-OPTIONAL")


def test_content_word_threshold_not_an_issue_on_a_valid_short_page():
    snap = snapshot('<html><head><title>Contact</title></head><body><h1>Контакты</h1><p>Телефон компании</p></body></html>')
    assert not issues(GeoAgent().run(snap), "GEO-CONTENT-REVIEW")


def test_query_coverage_only_with_user_query_and_keeps_low_confidence():
    snap = snapshot('<html><head><title>Каталог цветов</title></head><body><h1>Доставка букетов</h1></body></html>')
    assert not issues(GeoAgent().run(snap), "GEO-QUERY-COVERAGE")
    out = issues(GeoAgent(queries=["Внедрение ERP системы на промышленном предприятии"]).run(snap), "GEO-QUERY-COVERAGE")
    assert len(out) == 1 and out[0].confidence == "low" and out[0].status == "needs_review"


def test_very_short_js_initial_html_rendered_text_comparison():
    snap = snapshot('<html><head><script src="/app.js"></script></head><body><div id="app"></div></body></html>',
                    browser_evidence=[{"url": URL, "rendered_text_chars": 1500}])
    assert issues(GeoAgent().run(snap), "GEO-RENDER-DIFF")


def test_stable_identifiers_across_repeated_scans():
    html = '<html><form><input type="tel" name="phone"><label><input type="checkbox" checked>Согласие на обработку персональных данных</label></form></html>'
    a = LegalAgent().run(snapshot(html))
    b = LegalAgent().run(snapshot(html))
    assert [f.id for f in a] == [f.id for f in b]


def test_forms_do_not_leak_input_values_to_evidence():
    s = snapshot('<html><form><input type="email" name="email" value="person@example.org"><input type="password" value="secret123"></form></html>')
    assert "person@example.org" not in str(s.model_dump())
    assert "secret123" not in str(s.model_dump())
    assert "secret123" not in str([f.model_dump() for f in LegalAgent().run(s)])


def test_read_only_crawler_excludes_state_changing_url_patterns():
    assert BLOCKED_GET_PATHS.search("/account/delete/")
    assert BLOCKED_GET_PATHS.search("/user/logout")
    assert not BLOCKED_GET_PATHS.search("/products/details")
    assert strip_tracking("https://example.org/shop/?utm_id=a") == "https://example.org/shop/"
