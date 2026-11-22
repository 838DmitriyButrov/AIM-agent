"""Render audit records as a readable Markdown report."""
from __future__ import annotations

from collections import Counter

from .models import AuditReport, Finding


SCAN_STATUS = {
    "completed_sample": "Проверка выборки завершена.",
    "completed_sample_with_restrictions": "Проверка выборки завершена. Часть запросов получила отказ.",
    "blocked_network": "Сканирование не началось. Среда запуска не смогла подключиться к сайту.",
    "blocked_http": "Аудит не выполнен. Сервер отказал в доступе нашему агенту.",
    "rate_limited": "Аудит не выполнен. Сервер ограничил частоту запросов агента.",
    "blocked_robots": "Аудит не выполнен. Правила обхода не позволили получить страницы.",
    "no_pages": "Аудит не выполнен. Агент не получил HTML для проверки.",
}

IMPACT = {
    "GEO-SCHEMA-INVALID": "Поисковик может пропустить некорректный блок JSON-LD. Если в нём переданы цена, наличие или рейтинг, эти данные могут не попасть в расширенное представление результата. Влияние на позиции по этой ошибке не измерено.",
    "GEO-SCHEMA-TYPES": "Разметка помогает поисковым системам понять, какие сущности описаны на странице. Наличие типов само по себе не подтверждает право на расширенный результат или его показ.",
    "GEO-TITLE": "Поисковик может сформировать заголовок результата из других элементов страницы. В выдаче он может отличаться от того, что планировал сайт.",
    "GEO-DUP-TITLE": "Похожие заголовки могут мешать покупателю различать страницы в результатах поиска. Сначала стоит выяснить, должны ли эти страницы показываться отдельно.",
    "GEO-DESCRIPTION": "У поисковика нет подготовленного описания для сниппета. Он может подобрать текст со страницы. Индексацию один этот признак не блокирует.",
    "GEO-H1": "Если заголовка нет и после загрузки страницы, пользователю сложнее быстро понять её тему. Позиции по этому признаку не оценивались.",
    "GEO-H1-JS": "Главный заголовок доступен после выполнения JavaScript. Клиенты, которые читают только исходный HTML, его не увидят.",
    "GEO-CANONICAL": "Если поисковик примет указание, в выдаче может появиться другой адрес. Для дублей это может быть нормальным поведением.",
    "GEO-NOINDEX": "Поисковик, который прочитает и соблюдает директиву, может исключить URL из выдачи. На каких ботов она распространяется, указано выше.",
    "GEO-SNIPPET-RESTRICTION": "Указанная поисковая система может сократить текст под ссылкой или убрать его. Действие зависит от директивы и платформы.",
    "GEO-GOOGLE-EXTENDED-POLICY": "Правило касается использования контента в отдельных сценариях Gemini. Оно не меняет присутствие URL в Google Search.",
    "GEO-SITEMAP": "Карта сайта помогает поисковикам обнаруживать URL. Без неё обнаружение может сильнее зависеть от внутренних ссылок и других источников.",
    "GEO-RENDER-REVIEW": "Если основной текст загружается только через JavaScript, читатели исходного HTML могут получить неполное содержимое.",
    "GEO-RENDER-DIFF": "При чтении исходного HTML часть текста может быть недоступна. Видимость для конкретной поисковой системы нужно проверить отдельно.",
    "GEO-QUERY-COVERAGE": "Для заданного вопроса агент не нашёл совпадений в выборке. Проверка по словам может пропустить смысловые совпадения и не измеряет позиции.",
    "LEGAL-CONSUMER-INFO": "Если реквизиты действительно трудно найти перед заказом, покупателю сложнее понять, у кого он покупает и к кому обращаться по заказу или возврату.",
    "LEGAL-PD-POLICY": "Если политика недоступна рядом с формой, пользователю сложнее узнать, кто и зачем обрабатывает данные перед их отправкой.",
    "LEGAL-PD-CONSENT": "Если форма опирается на согласие, важно убедиться, что пользователь даёт его самостоятельным действием и понимает, на что соглашается.",
    "COOKIE-OBSERVATION": "Наблюдение показывает активность до взаимодействия с сайтом. Чтобы оценить её последствия, нужно определить назначение cookies и условия их использования.",
}

NEXT_STEP = {
    "GEO-SCHEMA-INVALID": "Найти ошибочный блок, исправить синтаксис и повторить проверку в валидаторе.",
    "GEO-SCHEMA-TYPES": "Если важен конкретный вид результата, проверить разметку страницы в инструменте поисковой системы.",
    "LEGAL-CONSUMER-INFO": "Открыть публичную оферту и проверить, где покупатель видит название, адрес и реквизиты продавца до оформления заказа.",
}

UNCHECKED_ACTION = {
    "GEO-AI-VISIBILITY": "Оценить цитирования по данным вебмастера или отдельному замеру.",
    "GEO-SITEMAP-UNVERIFIED": "Проверить, открывается ли объявленная карта и какие URL в неё включены.",
    "LEGAL-KKT": "Сверить выдачу чеков и порядок расчётов на реальных сценариях оплаты.",
    "LEGAL-LANGUAGE": "Проверить тексты интерфейса и применимость требований к ним.",
}

PHASE = {"robots": "правила обхода", "sitemap": "карта сайта", "page": "страница"}


def impact_for(finding: Finding) -> str:
    if finding.rule_id.startswith("GEO-") and finding.rule_id.endswith("-ROBOTS") and finding.rule_id != "GEO-ROBOTS":
        return "Правило ограничивает обход этого адреса указанным ботом. Само по себе оно не гарантирует исключение страницы из выдачи."
    return IMPACT.get(finding.rule_id, "По собранным данным влияние пока определить нельзя.")


def next_step(finding: Finding) -> str:
    return NEXT_STEP.get(finding.rule_id, " ".join(finding.action.split()))


def coverage_lines(report: AuditReport) -> list[str]:
    coverage = report.coverage
    lines = [SCAN_STATUS.get(coverage.get("scan_status"), "Результаты относятся к обследованным страницам."), ""]
    budget = coverage.get("max_pages_requested")
    lines.append(f"- Проверено страниц: **{report.pages_scanned}**" + (f" из {budget} запрошенных." if budget else "."))
    if coverage.get("crawl_limit_reached"):
        lines.append("- Достигнут лимит обхода. Часть ссылок осталась в очереди.")
    if coverage.get("browser_pages_probed") == 0:
        lines.append("- Проверен исходный HTML. Страницы после загрузки JavaScript не проверялись.")
    return lines


def finding_lines(findings: list[Finding], start: int = 1) -> list[str]:
    groups: dict[tuple, list[Finding]] = {}
    for finding in findings:
        key = (finding.agent, finding.rule_id, finding.title, finding.explanation, finding.action, finding.status)
        groups.setdefault(key, []).append(finding)

    lines = []
    for index, group in enumerate(groups.values(), start):
        first = group[0]
        lines += [f"### {index}. {first.title}", "",
                  f"**Что увидел агент.** {' '.join(first.explanation.split())}", "",
                  f"**На что это влияет.** {impact_for(first)}", "",
                  f"**Следующий шаг.** {next_step(first)}", ""]
        pages = dict.fromkeys(evidence.page for finding in group for evidence in finding.evidence if evidence.page)
        if pages:
            lines.append("**Где обнаружено**")
            lines.append("")
            lines.extend(f"- <{page}>" for page in pages)
            lines.append("")
        refs = dict.fromkeys(ref for finding in group for ref in finding.references)
        if refs:
            lines += ["Источники · " + " · ".join(f"[Документ {index}](<{ref}>)" for index, ref in enumerate(refs, 1)), ""]
    return lines


def crawl_note(note: str) -> str:
    if note == "Unable to check /sitemap.xml.":
        return "Не удалось проверить стандартный адрес карты сайта `/sitemap.xml`."
    if note.startswith("Disallowed by robots.txt: "):
        return f"Агент пропустил адрес по правилам robots.txt: <{note.split(': ', 1)[1]}>"
    return note


def to_markdown(report: AuditReport) -> str:
    counts = Counter(f.status for f in report.findings)
    needs_attention = [f for f in report.findings if f.status in {"potential_risk", "needs_review"}]
    observations = [f for f in report.findings if f.status == "observation"]
    unchecked = [f for f in report.findings if f.status == "not_tested"]
    passed = [f for f in report.findings if f.status == "passed"]
    lines = ["# Аудит сайта", "", f"**Сайт:** <{report.target}>",
             f"**Дата и время (UTC):** {report.scanned_at_utc:%Y-%m-%d %H:%M:%S}", "",
             "## Коротко", "", *coverage_lines(report),
             f"- Требуют внимания: **{len(needs_attention)}**. Это вопросы и потенциальные риски для проверки.",
             f"- Наблюдения: **{len(observations)}**.",
             f"- Остались без проверки: **{len(unchecked)}**.", ""]
    if report.access_diagnostics:
        lines += ["## Доступ к сайту", "",
                  "Коды ниже получены нашим агентом. По ним нельзя установить причину отказа или делать вывод о доступе поисковиков.", ""]
        lines.extend(f"- HTTP {item.status_code} · {PHASE[item.phase]} · <{item.url}>"
                     for item in report.access_diagnostics[:12])
        lines.append("")
    if needs_attention:
        lines += ["## Что требует внимания", "",
                  "Эти записи требуют проверки перед выводом о нарушении или влиянии на сайт.", ""]
        lines += finding_lines(needs_attention)
    if observations:
        lines += ["## Наблюдения", ""]
        lines += finding_lines(observations, len(needs_attention) + 1)
    if passed:
        lines += ["## Проверки без замечаний", "", *[f"- {item.title}" for item in passed], ""]
    if unchecked:
        lines += ["## Требования, которые не удалось проверить", ""]
        lines += [f"- **{item.title}.** {UNCHECKED_ACTION.get(item.rule_id, item.action)}" for item in unchecked]
        lines.append("")
    if not report.findings and report.pages_scanned:
        lines += ["## Находки", "", "В обследованных страницах агент не отметил проблем. Проверка охватывала только эту выборку.", ""]
    notes = [crawl_note(note) for note in report.crawl_notes if not note.startswith("Limited sample:")]
    if notes:
        lines += ["## Что ограничило обход", "", *[f"- {note}" for note in notes], ""]
    if report.disclaimers:
        lines += ["## Ограничения", "", *[f"- {limit}" for limit in report.disclaimers], ""]
    lines += ["Подробные данные о проверках, свидетельства и коды правил доступны в JSON-отчёте."]
    return "\n".join(lines) + "\n"
