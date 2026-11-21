"""Diagnose direct internet access without DNS bypasses or website crawling.

This is an environment check, not a universal network reachability test.
A successful public TCP connection doesn't imply the target site is reachable.
"""
from __future__ import annotations
import socket
from urllib.parse import urlparse
from .crawler import validate_public_url, DNSResolutionError, UnsafeTarget

# Known public test endpoint. A blocked connection is evidence of egress restriction,
# not a reason to bypass sandbox/network policies.
PUBLIC_TCP_PROBE = ("1.1.1.1", 443)


def diagnose_network(target: str = "https://example.com/", timeout: float = 2.0) -> dict[str, str]:
    """Check target DNS and direct public TCP; no page requests or DNS overrides."""
    dns_status = "ok"
    try:
        validate_public_url(target)
    except DNSResolutionError as exc:
        dns_status = exc.code
    except UnsafeTarget:
        raise
    except ValueError:
        raise
    try:
        with socket.create_connection(PUBLIC_TCP_PROBE, timeout=timeout):
            egress_status = "ok"
    except OSError as exc:
        egress_status = f"blocked_or_unavailable ({type(exc).__name__})"

    if dns_status == "DNS_TEMPORARY" and egress_status != "ok":
        diagnosis = ("DNS and direct outbound TCP are unavailable; likely a sandbox/hosting network policy. "
                     "Use a network-enabled authorized runner or have its administrator configure DNS and egress. "
                     "Do not disable target IP validation.")
    elif dns_status == "DNS_TEMPORARY":
        diagnosis = "Public TCP is reachable but DNS is unavailable. Inspect runner's resolver and DNS firewall."
    elif dns_status == "DNS_NOT_FOUND":
        diagnosis = "Target hostname did not resolve; check domain spelling and authoritative DNS."
    elif dns_status == "ok" and egress_status != "ok":
        diagnosis = ("Target DNS works, but the fixed public TCP probe was blocked. "
                     "Investigate outbound networking; this probe alone does not prove that HTTPS to the target is blocked.")
    else:
        diagnosis = "Target DNS and fixed public TCP probe are available; retry the scan."
    return {"target": target, "host": urlparse(target).hostname or "",
            "dns_status": dns_status, "egress_status": egress_status, "diagnosis": diagnosis}
