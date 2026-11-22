"""Private staging API: access token + fixed target allowlist; requires network SSRF isolation."""
from __future__ import annotations

import hmac
import os
import threading
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .orchestrator import run_audit
from .search_results import SearchSnapshot

app = FastAPI(title="Site Audit Agents", version="0.2.4",
              description="Restricted LEGAL and GEO audit API; no public multitenant exposure")


SCAN_SEMAPHORE = threading.BoundedSemaphore(value=1)  # single worker guard (not cluster-wide)


class ScanRequest(BaseModel):
    url: str
    agents: list[str] = Field(default_factory=lambda: ["legal", "geo"])
    max_pages: int = Field(default=8, ge=1, le=8)
    search_snapshots: list[SearchSnapshot] | None = Field(default=None, max_length=5)


@app.get("/health")
def health():
    return {"status": "ok", "agents_ready": ["legal", "geo"], "agents_reserved": ["ux"]}


def require_private_access(request: Request, url: str) -> None:
    """Fail closed without configuration; network-level SSRF protection still required."""
    secret = os.getenv("AUDIT_TOKEN", "")
    hosts = {h.strip().lower().rstrip(".") for h in
             os.getenv("AUDIT_ALLOWED_HOSTS", "").split(",") if h.strip()}
    if len(secret) < 32 or not hosts:
        raise HTTPException(status_code=503,
                            detail="Audit API is disabled: configure AUDIT_TOKEN and AUDIT_ALLOWED_HOSTS")
    provided = request.headers.get("authorization", "")
    prefix = "Bearer "
    token = provided[len(prefix):] if provided.startswith(prefix) else ""
    if not hmac.compare_digest(secret, token):
        raise HTTPException(status_code=401, detail="Unauthorized",
                            headers={"WWW-Authenticate": "Bearer"})
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower().rstrip(".") not in hosts:
        raise HTTPException(status_code=403, detail="Host not approved for this staging audit")
    try:
        port = parsed.port
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid port") from None
    if parsed.username or parsed.password or port not in {None, 443}:
        raise HTTPException(status_code=403, detail="Credentials and nonstandard ports are forbidden")


@app.post("/scan")
def scan(req: ScanRequest, request: Request):
    require_private_access(request, req.url)
    if not SCAN_SEMAPHORE.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Audit worker busy; retry later")
    try:
        try:
            search_options = {"search_snapshots": req.search_snapshots} if req.search_snapshots else {}
            report = run_audit(req.url, req.agents, req.max_pages, **search_options)
            if report.coverage.get("scan_status") == "blocked_network":
                return JSONResponse(status_code=503, content=report.model_dump(mode="json"))
            return report
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502,
                                detail=f"Audit unavailable: {type(exc).__name__}") from exc
    finally:
        SCAN_SEMAPHORE.release()
