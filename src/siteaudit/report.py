"""Portable machine-readable and concise human-readable audit reports."""
from __future__ import annotations
from collections import Counter
from .models import AuditReport


def to_markdown(report: AuditReport) -> str:
    counts = Counter(f.status for f in report.findings)
    lines = ["# Аудит сайта", "", f"**URL:** {report.target}",
             f"**Дата (UTC):** {report.scanned_at_utc.isoformat()}",
             f"**Агенты:** {', '.join(a.upper() for a in report.agents)}",
             f"**Страниц исследовано:** {report.pages_scanned}",
             f"**Потенциальных рисков:** {counts['potential_risk']}",
             f"**На ручной проверке:** {counts['needs_review']}",
             f"**Не проверено:** {counts['not_tested']}",
             "", "## Охват проверки", ""]
    lines += [f"- {key}: {value}" for key, value in report.coverage.items()]
    if report.coverage.get("scan_status") == "blocked_network":
        lines += ["", "**Сканирование не началось: сетевая/DNS-недоступность среды запуска.**", "",
                  "Это не является обнаруженной проблемой сайта и не даёт оснований делать вывод о его соответствии.", ""]
    lines += ["", "## Находки", ""]
    for idx, f in enumerate(report.findings, 1):
        lines += [f"### {idx}. {f.title}",
                  f"**{f.agent.upper()} · {f.rule_id} · {f.status} · {f.severity} · уверенность: {f.confidence}**",
                  f"**Применимость:** {f.applicability}; **уровень доказательств:** {f.evidence_level}", "",
                  f.explanation.replace("\n", " "), "",
                  f"**Рекомендация:** {f.action.replace(chr(10), ' ')}", ""]
        for evidence in f.evidence:
            lines.append(f"- Доказательство ({evidence.kind}): {evidence.page} — {evidence.detail.replace(chr(10), ' ')[:250]}")
            if evidence.source_sha256:
                lines.append(f"  - SHA-256 исходного HTML: `{evidence.source_sha256}`")
        for ref in f.references:
            lines.append(f"- Источник: {ref}")
        lines.append("")
    if not report.findings and report.pages_scanned:
        lines += ["*Автоматически проверяемых проблем не найдено в полученной выборке. Это не подтверждает соответствие требованиям.*", ""]
    elif not report.findings:
        lines += ["*Находок нет, поскольку страницы не были исследованы.*", ""]
    lines += ["## Ограничения", ""]
    lines += [f"- {d}" for d in report.disclaimers]
    if report.crawl_notes:
        lines += ["", "## Замечания краулера", ""] + [f"- {note}" for note in report.crawl_notes]
    return "\n".join(lines) + "\n"
