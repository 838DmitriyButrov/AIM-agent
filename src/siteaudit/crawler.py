"""Bounded, same-site, read-only HTTP crawler; production requires an egress firewall.

This is NOT SSRF-hardening sufficient for a public multitenant service: DNS rebinding
can occur between validation and the HTTP connection. Run in an isolated environment.
"""
from __future__ import annotations
import ipaddress
import posixpath
import re
import socket
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
import httpx
from .extract import parse_page
from .models import SiteSnapshot

USER_AGENT = "SiteAuditAgents/0.2.1 (+authorized read-only website audit)"
MAX_RESPONSE_BYTES = 2_000_000
BLOCKED_GET_PATHS = re.compile(r"/(?:logout|signout|delete|remove|unsubscribe|confirm|destroy|terminate)(?:/|$)", re.I)


class UnsafeTarget(ValueError):
    """The requested target is outside the safe public crawling scope."""


class DNSResolutionError(ConnectionError):
    """DNS couldn't be resolved; distinguish network issues from unsafe URLs."""

    def __init__(self, hostname: str, code: str):
        self.hostname = hostname
        self.code = code
        messages = {
            "DNS_TEMPORARY": "DNS service is temporarily unavailable or unreachable",
            "DNS_NOT_FOUND": "Domain name does not resolve (NXDOMAIN or no usable record)",
            "DNS_ERROR": "DNS lookup failed",
        }
        super().__init__(f"{messages.get(code, messages['DNS_ERROR'])} for {hostname}")


def validate_public_url(url: str) -> str:
    """Basic URL + DNS guard. Do not expose publicly without IP-pinning / egress control."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeTarget("Only public http(s) URLs without credentials are supported")
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeTarget("Invalid port") from exc
    if port not in {None, 80, 443}:
        raise UnsafeTarget("Non-standard ports are not allowed")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        raise UnsafeTarget("Local domains are not allowed")
    try:
        infos = socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        if exc.errno == getattr(socket, "EAI_AGAIN", -3):
            code = "DNS_TEMPORARY"
        elif exc.errno == getattr(socket, "EAI_NONAME", -2):
            code = "DNS_NOT_FOUND"
        else:
            code = "DNS_ERROR"
        raise DNSResolutionError(host, code) from exc
    if not infos:
        raise DNSResolutionError(host, "DNS_NOT_FOUND")
    for info in infos:
        address = info[4][0]
        if not ipaddress.ip_address(address.split("%")[0]).is_global:
            raise UnsafeTarget("Private, loopback, reserved or link-local targets are forbidden")
    return url


def strip_tracking(url: str) -> str:
    p = urlparse(url)
    # v0.2 default intentionally does not crawl query parameters; can miss valuable product pages.
    path = posixpath.normpath(p.path or "/")
    if p.path.endswith("/") and path != "/":
        path += "/"
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))


class SiteCrawler:
    def __init__(self, max_pages: int = 12, delay: float = 0.2):
        self.max_pages = min(max(1, max_pages), 50)
        self.delay = max(0.0, delay)
        self.max_attempts = min(self.max_pages * 5, 200)

    def _read(self, client: httpx.Client, url: str, max_bytes: int = MAX_RESPONSE_BYTES,
              allowed_hosts: set[str] | None = None) -> tuple[int, str, str, dict[str, str]]:
        current = url
        for _ in range(5):
            validate_public_url(current)
            if allowed_hosts is not None and urlparse(current).hostname not in allowed_hosts:
                raise UnsafeTarget("Redirect outside approved host scope")
            with client.stream("GET", current, follow_redirects=False) as res:
                headers = {k.lower(): v for k, v in res.headers.items() if k.lower() in {"content-type", "x-robots-tag"}}
                if res.status_code in {301, 302, 303, 307, 308}:
                    location = res.headers.get("location")
                    if not location:
                        return res.status_code, current, "", headers
                    current = urljoin(current, location)
                    continue
                content = bytearray()
                for chunk in res.iter_bytes(8192):
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise ValueError("Response exceeds size limit")
                return res.status_code, str(res.url), bytes(content).decode(res.encoding or "utf-8", errors="replace"), headers
        raise ValueError("Too many redirects")

    def crawl(self, target: str) -> SiteSnapshot:
        validate_public_url(target)
        start = strip_tracking(target)
        original_host = urlparse(start).hostname or ""
        bare = original_host.removeprefix("www.")
        allowed_hosts = {bare, f"www.{bare}"} if original_host in {bare, f"www.{bare}"} else {original_host}
        notes: list[str] = []
        pages = []
        seen: set[str] = set()
        queue = deque([start])
        robots_txt = None
        sitemap_found = None
        sitemap_status = None
        declared: list[str] = []
        robot = RobotFileParser()
        with httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                          timeout=12, trust_env=False) as client:
            base = f"{urlparse(start).scheme}://{urlparse(start).netloc}"
            try:
                status, _, content, _ = self._read(client, urljoin(base, "/robots.txt"),
                                                   max_bytes=512_000, allowed_hosts=allowed_hosts)
                if status == 200:
                    robots_txt = content
                    robot.parse(content.splitlines())
                    for line in content.splitlines():
                        if re.match(r"^\s*Sitemap\s*:", line, re.I):
                            address = line.split(":", 1)[1].strip()
                            if urlparse(address).scheme in {"http", "https"}:
                                declared.append(address)
                elif status in {404, 410}:
                    robot.parse([])
                else:
                    return SiteSnapshot(input_url=target, final_url=start,
                                        crawl_notes=[f"robots.txt returned HTTP {status}; stopped conservatively."])
            except (httpx.HTTPError, ValueError, UnsafeTarget, DNSResolutionError) as exc:
                code = f"{exc.code}: " if isinstance(exc, DNSResolutionError) else ""
                return SiteSnapshot(input_url=target, final_url=start,
                                    crawl_notes=[f"{code}robots.txt unavailable ({type(exc).__name__}: {exc}); stopped conservatively."])
            try:
                sitemap_status, _, sitemap_body, _ = self._read(
                    client, urljoin(base, "/sitemap.xml"), max_bytes=1_000_000, allowed_hosts=allowed_hosts)
                sitemap_found = (sitemap_status == 200 and
                                 bool(re.search(r"<\s*(?:\w+:)?(?:urlset|sitemapindex)\b", sitemap_body[:1000], re.I)))
                if sitemap_status == 200 and not sitemap_found:
                    notes.append("/sitemap.xml responded HTTP 200 but did not look like an XML sitemap.")
            except (httpx.HTTPError, ValueError, UnsafeTarget, DNSResolutionError):
                notes.append("Unable to check /sitemap.xml.")

            while queue and len(pages) < self.max_pages and len(seen) < self.max_attempts:
                current = strip_tracking(queue.popleft())
                if current in seen:
                    continue
                seen.add(current)
                parsed = urlparse(current)
                if parsed.hostname not in allowed_hosts or parsed.scheme not in {"https", "http"}:
                    continue
                if BLOCKED_GET_PATHS.search(parsed.path):
                    notes.append(f"Potentially state-changing GET not visited: {current}")
                    continue
                if not robot.can_fetch(USER_AGENT, current):
                    notes.append(f"Disallowed by robots.txt: {current}")
                    continue
                try:
                    status, final, body, headers = self._read(client, current, allowed_hosts=allowed_hosts)
                    if urlparse(final).hostname not in allowed_hosts:
                        notes.append(f"Out-of-scope redirect skipped: {current}")
                        continue
                    if status != 200:
                        notes.append(f"HTTP {status} at {current}")
                        continue
                    content_type = headers.get("content-type", "").lower()
                    if content_type and "html" not in content_type:
                        notes.append(f"Non-HTML Content-Type skipped: {current}")
                        continue
                    if "<html" not in body[:20000].lower():
                        notes.append(f"Non-HTML response skipped: {current}")
                        continue
                    page = parse_page(final, status, body, headers)
                    pages.append(page)
                    for link in page.internal_links[:150]:
                        clean = strip_tracking(link)
                        if urlparse(clean).hostname in allowed_hosts and clean not in seen and len(queue) < 1000:
                            queue.append(clean)
                except (httpx.HTTPError, ValueError, UnsafeTarget, DNSResolutionError, UnicodeError) as exc:
                    notes.append(f"Skipped {current}: {type(exc).__name__}: {str(exc)[:160]}")
                if self.delay:
                    time.sleep(self.delay)
        limited = bool(queue) and (len(pages) >= self.max_pages or len(seen) >= self.max_attempts)
        if limited:
            notes.append(f"Limited sample: fetched {len(pages)} pages, tried {len(seen)} URLs. Absence != compliance.")
        return SiteSnapshot(input_url=target, final_url=pages[0].url if pages else start, pages=pages,
                            robots_txt=robots_txt, sitemap_found=sitemap_found,
                            sitemap_status=sitemap_status, sitemap_declared=declared,
                            crawl_limit_reached=limited, crawl_notes=notes)
