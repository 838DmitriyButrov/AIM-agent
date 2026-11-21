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
             f"**Информационных наблюдений:** {counts['observation']}",
             f"**Непроверенных требований (НЕ проблемы):** {counts['not_tested']}",
             "", "## Охват проверки", ""]
    lines += [f"- {key}: {value}" for key, value in report.coverage.items()]
    if report.coverage.get("scan_status") == "blocked_network":
        lines += ["", "**Сканирование не началось: сетевая/DNS-недоступность среды запуска.**", "",
                  "Это не является обнаруженной проблемой сайта и не даёт оснований делать вывод о его соответствии.", ""]
    if report.coverage.get("scan_status") in {"blocked_http", "rate_limited", "blocked_robots"}:
        lines += ["", "**Аудит не выполнен из-за ограничений доступа или robots.txt.**", "",
                  "HTTP 401/403/429 относится к ответу, полученному нашим краулером; причина не установлена, "
                  "и это не доказательство SEO-проблемы или правового нарушения.", ""]
    if report.access_diagnostics:
        lines += ["", "## HTTP-диагностика доступа (без cookies и токенов)", ""]
        for item in report.access_diagnostics[:12]:
            lines += [
                f"- **HTTP {item.status_code}**, фаза `{item.phase}`: {item.url}",
                f"  - Категория: {item.response_class}; Content-Type: {item.content_type or 'неизвестен'}",
                f"  - Схемы WWW-Authenticate: {', '.join(item.auth_schemes) if item.auth_schemes else 'не указаны'}; "
                f"признак сервера/CDN: {item.server_hint}; идентификатор CDN: {item.has_cdn_request_id}",
                f"  - Признаки страницы ответа: {', '.join(item.challenge_indicators) if item.challenge_indicators else 'не определены'}; "
                f"байтов: {item.response_body_bytes}; SHA-256: {item.body_sha256}",
                "  - **Интерпретация:** причина отказа не подтверждена. Для дальнейшего доступа требуется разрешённый способ проверки.",
            ]
    # Preserve every record in JSON, but never label untested requirements as defects.
    reviewable = [item for item in report.findings if item.status != "not_tested"]
    unchecked = [item for item in report.findings if item.status == "not_tested"]
    lines += ["", "## Наблюдения и потенциальные риски", "",
              "Эти записи не являются установленными нарушениями.", ""]

    for idx, f in enumerate(reviewable, 1):
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
    if unchecked:
        lines += ["", "## Требования, которые не удалось проверить", "",
                  "Не включаются в число обнаруженных проблем.", ""]
        for item in unchecked:
            lines += [f"- **{item.rule_id}** — {item.title}. {item.action}"]
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
