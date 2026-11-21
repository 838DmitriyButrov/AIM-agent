"""Opt-in passive browser probe; no clicks, submissions, storage values or screenshots."""
from __future__ import annotations
from urllib.parse import urlparse
from .crawler import validate_public_url


def passive_browser_probe(url: str) -> dict:
    from playwright.sync_api import sync_playwright
    validate_public_url(url)
    requested_hosts: set[str] = set()
    completed_hosts: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(service_workers="block", accept_downloads=False)
        page = context.new_page()

        def gate(route):
            request = route.request
            try:
                # No POST/PUT and no nonpublic destinations (including subresources).
                if request.method != "GET":
                    route.abort()
                else:
                    validate_public_url(request.url)
                    route.continue_()
            except Exception:
                route.abort()

        page.route("**/*", gate)
        page.on("request", lambda req: requested_hosts.add(urlparse(req.url).hostname or ""))
        page.on("requestfinished", lambda req: completed_hosts.add(urlparse(req.url).hostname or ""))
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(750)
            cookies = [{"name": c["name"], "domain": c["domain"]} for c in context.cookies()]
            return {"url": page.url, "requests_to_domains": sorted(requested_hosts),
                    "completed_request_domains": sorted(completed_hosts),
                    "cookies_before_interaction": cookies,
                    "rendered_text_chars": len(page.locator("body").inner_text(timeout=3000)[:100000]),
                    "rendered_title": page.title(),
                    "note": "Passive first-page observation. Cookie values, form values and screenshots not recorded. "
                            "Requests can still have third-party effects; run only on authorized websites."}
        finally:
            browser.close()
