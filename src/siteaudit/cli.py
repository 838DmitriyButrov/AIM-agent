"""CLI entrypoint; e.g. siteaudit scan https://example.com --max-pages 10."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .orchestrator import run_audit
from .report import to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="siteaudit", description="LEGAL + AI Search/GEO scanner (prototype)")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Diagnose DNS and direct outbound TCP; does not crawl sites")
    doctor.add_argument("url", nargs="?", default="https://example.com/", help="Public URL to validate DNS for")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable diagnostic result")
    scan = commands.add_parser("scan", help="Read-only audit of a public site")
    scan.add_argument("url", help="Public http(s) URL; no private addresses")
    scan.add_argument("--agent", action="append", choices=["legal", "geo"], help="Repeat to select agents (default: both)")
    scan.add_argument("--max-pages", type=int, default=12, help="1..50 public HTML pages")
    scan.add_argument("--browser", action="store_true", help="Optional passive Playwright observation; Chromium required")
    scan.add_argument("--ai", action="store_true", help="Explicitly send selected public excerpts to OpenAI for advisory review")
    scan.add_argument("--query", action="append", default=[], help="Target search question for AI analysis; repeatable")
    scan.add_argument("--out", type=Path, default=Path("reports/audit"), help="Output prefix for .json and .md files")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        from .network import diagnose_network
        try:
            result = diagnose_network(args.url)
        except Exception as exc:
            print(f"Diagnostic failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Target: {result['target']}")
            print(f"DNS: {result['dns_status']}")
            print(f"Direct outbound TCP: {result['egress_status']}")
            print(f"Diagnosis: {result['diagnosis']}")
        return 0 if result["dns_status"] == "ok" and result["egress_status"] == "ok" else 2
    if args.command == "scan":
        try:
            report = run_audit(args.url, agents=args.agent, max_pages=args.max_pages, with_browser=args.browser,
                               with_ai=args.ai, queries=args.query)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            json_path = Path(f"{args.out}.json")
            markdown_path = Path(f"{args.out}.md")
            json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            markdown_path.write_text(to_markdown(report), encoding="utf-8")
            print(f"Scanned {report.pages_scanned} pages; found {len(report.findings)} audit records.")
            print(f"Reports: {json_path} | {markdown_path}")
            if report.coverage.get("scan_status") == "blocked_network":
                print("NETWORK BLOCK: no audit performed. Run `siteaudit doctor` in a network-enabled environment.", file=sys.stderr)
            return 0 if report.pages_scanned else 2
        except Exception as exc:
            print(f"Audit failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
