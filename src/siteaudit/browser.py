"""Opt-in, read-only browser observation for authorized domains only.

This is NOT a WAF/CAPTCHA bypass and requires network-level egress isolation.
No user authentication, clicks, form submission, cookie values, or screenshots.
"""
from __future__ import annotations
from urllib.parse import urlparse
from .crawler import validate_public_url, BLOCKED_GET_PATHS, strip_tracking


def allowed_passive_request(url: str, method: str, initial_url: str) -> bool:
    """Fail closed on subresources outside the authorized host or on unsafe GET paths."""
    if method.upper() != "GET":
        return False
    initial = urlparse(initial_url)
    requested = urlparse(url)
    root = (initial.hostname or "").removeprefix("www.")
    if requested.scheme != "https" or requested.hostname not in {root, "www." + root}:
        return False
    if BLOCKED_GET_PATHS.search(requested.path):
        return False
    try:
        validate_public_url(url)
        return True
    except (ValueError, ConnectionError):
        return False


def passive_browser_probe(url: str) -> dict:
    from playwright.sync_api import sync_playwright
    validate_public_url(url)
    requested_hosts: set[str] = set()
    completed_hosts: set[str] = set()
    blocked_requests = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(service_workers="block", accept_downloads=False)
        page = context.new_page()

        def gate(route):
            nonlocal blocked_requests
            request = route.request
            if allowed_passive_request(request.url, request.method, url):
                # Browser redirects are not an SSRF firewall. Egress must be isolated independently.
                route.continue_()
            else:
                blocked_requests += 1
                route.abort()

        context.route("**/*", gate)
        page.on("request", lambda req: requested_hosts.add(urlparse(req.url).hostname or ""))
        page.on("requestfinished", lambda req: completed_hosts.add(urlparse(req.url).hostname or ""))
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(750)
            cookies = [{"name": c["name"], "domain": c["domain"]} for c in context.cookies()]
            headings = [h.strip()[:180] for h in page.locator("h1").all_text_contents()
                        if h.strip()][:5]
            return {
                "url": strip_tracking(page.url),
                "main_document_status": response.status if response else None,
                "requests_to_domains": sorted(requested_hosts),
                "completed_request_domains": sorted(completed_hosts),
                "requests_blocked_by_policy": blocked_requests,
                "cookies_before_interaction": cookies,
                "rendered_text_chars": len(page.locator("body").inner_text(timeout=3000)[:100000]),
                "rendered_title": page.title()[:300],
                "rendered_h1_count": page.locator("h1").count(),
                "rendered_h1_text": headings,
                "note": "Opt-in, read-only observation on approved host. Third-party resources and non-GET methods blocked. "
                        "Browser scripts may still have GET side effects; only run on authorized websites. "
                        "Not a CAPTCHA/WAF bypass. Requires outbound network isolation.",
            }
        finally:
            browser.close()
