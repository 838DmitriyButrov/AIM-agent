"""One-time, read-only benchmark for approved example domains.

Run with: python -m siteaudit.benchmark
Do not claim that an inaccessible site passed any audit.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from collections import Counter
from siteaudit.orchestrator import run_audit

SITES = {
    "lenta": "https://lenta.com/",
    "metro": "https://metro-cc.ru/",
    "auchan": "https://www.auchan.ru/",
}

def emit(kind: str, payload: dict) -> None:
    print(kind + " " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str), flush=True)

def main() -> int:
    emit("BENCHMARK_START", {"utc": datetime.now(timezone.utc).isoformat(),
                            "sites": list(SITES), "max_pages_per_site": 3,
                            "agents": ["legal", "geo"], "browser": False, "ai": False,
                            "read_only": True})
    for name, url in SITES.items():
        emit("SCAN_START", {"site": name, "url": url})
        try:
            report = run_audit(url, agents=["legal", "geo"], max_pages=3)
            fields = []
            for finding in report.findings[:60]:
                fields.append({
                    "agent": finding.agent, "rule_id": finding.rule_id,
                    "title": finding.title, "status": finding.status,
                    "severity": finding.severity, "confidence": finding.confidence,
                    "applicability": finding.applicability,
                    "explanation": finding.explanation[:350],
                    "action": finding.action[:180],
                    "references": finding.references[:3],
                    "evidence": [{"page": e.page, "kind": e.kind,
                                  "detail": e.detail[:180]} for e in finding.evidence[:2]],
                })
            emit("SCAN_RESULT", {
                "site": name, "url": url,
                "version": report.version,
                "scanned_at_utc": report.scanned_at_utc.isoformat(),
                "pages_scanned": report.pages_scanned,
                "coverage": report.coverage,
                "notes": report.crawl_notes[:25],
                "http_access": [d.model_dump(mode="json") for d in report.access_diagnostics[:12]],
                "methods": report.methods,
                "total_findings": len(report.findings),
                "status_counts": dict(Counter(f.status for f in report.findings)),
                "agent_counts": dict(Counter(f.agent for f in report.findings)),
                "findings": fields
            })
        except Exception as exc:
            emit("SCAN_ERROR", {"site": name, "error_type": type(exc).__name__,
                                "message": str(exc)[:400]})
    emit("BENCHMARK_DONE", {"utc": datetime.now(timezone.utc).isoformat()})
    return 0

if __name__ == "__main__":
    sys.exit(main())
