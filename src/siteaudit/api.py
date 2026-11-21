"""LOCAL DEVELOPMENT API ONLY. Do NOT publicly expose without egress firewall and auth."""
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .orchestrator import run_audit

app = FastAPI(title="Site Audit Agents", version="0.2.1",
              description="Development-only, read-only LEGAL and GEO audit API")


class ScanRequest(BaseModel):
    url: str
    agents: list[str] = Field(default_factory=lambda: ["legal", "geo"])
    max_pages: int = Field(default=8, ge=1, le=25)


@app.get("/health")
def health():
    return {"status": "ok", "agents_ready": ["legal", "geo"], "agents_reserved": ["ux"]}


@app.post("/scan")
def scan(req: ScanRequest):
    try:
        report = run_audit(req.url, req.agents, req.max_pages)
        if report.coverage.get("scan_status") == "blocked_network":
            return JSONResponse(status_code=503, content=report.model_dump(mode="json"))
        return report
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Audit unavailable: {type(exc).__name__}") from exc
