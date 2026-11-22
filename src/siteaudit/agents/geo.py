"""GEO/SEO: eligibility, fetchability, evidence-based query fit, never ranking claims."""
from __future__ import annotations
import re
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from ..finding_utils import evidence_from_page, issue_id
from ..models import Evidence, Finding, Page, SiteSnapshot

GOOGLE = "https://developers.google.com/search/docs/fundamentals/ai-optimization-guide"
GOOGLE_AI = "https://developers.google.com/search/docs/appearance/ai-features"
GOOGLE_ROBOTS = "https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag"
GOOGLE_SCHEMA = "https://developers.google.com/search/docs/appearance/structured-data/sd-policies"
YANDEX = "https://yandex.ru/support/webmaster/ru/service/alice-answers"
YANDEX_GUIDE = "https://yandex.ru/support/webmaster/ru/epos"
WORD_RE = re.compile(r"[\w-]{3,}", re.U)
STOPWORDS = {
    "какие", "какой", "какая", "какую", "где", "когда", "можно", "лучше", "нужно", "чтобы",
    "этого", "того", "сайте", "сайт", "который", "есть", "для", "как", "что", "это", "или",
    "а", "в", "и", "на", "с", "по", "от", "за", "из", "к", "у", "о", "не", "но", "да", "же", "бы", "ли", "то", "так"
}


def terms(value: str) -> set[str]:
    """Improved lexical tokens for Russian: longer stems, more stopwords, still not a full lemmatizer."""
    return {w.lower()[:8] for w in WORD_RE.findall(value.lower()) if w.lower() not in STOPWORDS and len(w) >= 3}


def has_directive(directives: str, directive: str) -> bool:
    return bool(re.search(r"(?:^|[,\s])" + re.escape(directive) + r"(?:$|[,\s:])", directives.lower()))


class GeoAgent:
    name = "geo"

    def __init__(self, queries: list[str] | None = None):
        self.queries = [q.strip()[:250] for q in (queries or []) if q.strip()][:20]

    def run(self, snapshot: SiteSnapshot) -> list[Finding]:
        findings: list[Finding] = []

        def add(rule: str, title: str, explanation: str, severity: str, page: Page | str,
                status: str, confidence: str, action: str, refs: list[str] | None = None,
                kind: str = "DOM", context: str = "", evidence_level: str = "indicative"):
            url = page.url if isinstance(page, Page) else page
            evidence = (evidence_from_page(page, kind, explanation) if isinstance(page, Page)
                        else Evidence(page=url, kind=kind, detail=explanation[:600]))
            findings.append(Finding(
                id=issue_id("geo", rule, url, context), agent="geo", rule_id=rule,
                title=title, explanation=explanation, severity=severity, status=status,
                confidence=confidence, applicability="conditional", evidence_level=evidence_level,
                evidence=[evidence], references=refs or [GOOGLE, YANDEX_GUIDE], action=action,
                needs_human_review=(status in {"needs_review", "not_tested"}),
            ))

        if not snapshot.pages:
            add("GEO-CRAWL", "Нет доступных страниц", "Публичный обход не получил HTML-страниц — оценка GEO/SEO не выполнена.",
                "high", snapshot.input_url, "not_tested", "high", "Проверить robots.txt, сеть и доступность сайта.", evidence_level="insufficient")
            return findings

        if snapshot.sitemap_found is False and not snapshot.sitemap_declared:
            add("GEO-SITEMAP", "Не обнаружена карта сайта по стандартному адресу или в robots.txt",
                "По адресу /sitemap.xml не найдена XML-карта; в robots.txt нет директив Sitemap. "
                "Карта сайта не обязательна и может быть доступна по другому адресу.",
                "low", snapshot.final_url, "observation", "high", "При необходимости указать XML sitemap в robots.txt.",
                evidence_level="direct")
        elif snapshot.sitemap_declared and not snapshot.sitemap_found:
            add("GEO-SITEMAP-UNVERIFIED", "Обнаружена декларация Sitemap — содержимое не проверено",
                "robots.txt содержит Sitemap, но стандартный /sitemap.xml не подтверждён; это не означает отсутствие карты.",
                "info", snapshot.final_url, "not_tested", "high", "Проверить заявленный sitemap, формат, доступность и фактический состав URL.",
                evidence_level="insufficient")
        if snapshot.robots_txt is None:
            add("GEO-ROBOTS", "Неизвестно состояние robots.txt", "Не удалось проверить robots.txt; это ограничение проверки, а не доказательство запрета индексации.",
                "info", snapshot.final_url, "not_tested", "high", "Повторить проверку robots.txt.", evidence_level="insufficient")

        robot = RobotFileParser()
        if snapshot.robots_txt is not None:
            robot.parse(snapshot.robots_txt.splitlines())

        seen_titles: dict[str, str] = {}
        pages_by_url = {p.url.rstrip("/"): p for p in snapshot.pages}
        for page in snapshot.pages:
            if snapshot.robots_txt is not None:
                bots = [
                    ("GOOGLEBOT", "Googlebot"),
                    ("YANDEXBOT", "YandexBot"),
                    ("OAI-SEARCHBOT", "OAI-SearchBot"),
                    ("CLAUDE-SEARCHBOT", "Claude-SearchBot"),
                    ("PERPLEXITYBOT", "PerplexityBot"),
                    ("GOOGLE-EXTENDED", "Google-Extended"),
                ]
                for name, user_agent in bots:
                    if not robot.can_fetch(user_agent, page.url):
                        severity = "medium" if name in {"GOOGLEBOT", "YANDEXBOT"} else "low"
                        add(f"GEO-{name}-ROBOTS", f"robots.txt запрещает доступ для {user_agent}",
                            f"В robots.txt crawler {user_agent} не имеет доступа к {page.url}. "
                            "Если страница должна участвовать в поиске или AI-ответах, проверьте правило; robots.txt сам по себе не гарантирует деиндексацию.",
                            severity, page, "observation", "high", "Проверить целевую аудиторию, правило Disallow и назначение страницы.",
                            [GOOGLE_ROBOTS, YANDEX_GUIDE, GOOGLE_AI], "robots.txt", evidence_level="direct")
            # Generic and bot-scoped meta must remain distinguishable. A Googlebot
            # directive is not evidence that all search engines are restricted.
            generic_directives = [d for d in [page.robots_meta, page.x_robots_tag] if d]
            scoped_directives = [(bot, d) for bot, d in page.robots_meta_by_agent.items() if d]
            noindex = [(name, d) for name, d in
                       [("all bots", d) for d in generic_directives] + scoped_directives
                       if has_directive(d, "noindex") or has_directive(d, "none")]
            if noindex:
                scopes = ", ".join(name for name, _ in noindex)
                excerpt = "; ".join(f"{name}: {value}" for name, value in noindex)[:300]
                add("GEO-NOINDEX", "Обнаружена директива noindex",
                    f"Сфера действия: {scopes}. meta robots / X-Robots-Tag: {excerpt}. "
                    "Это не подтверждает отсутствие в индексе всех поисковых систем.",
                    "medium", page, "observation", "high",
                    "Проверить намерение по каждому конкретному поисковому боту и статус индексации.",
                    [GOOGLE_ROBOTS], "HTTP+DOM", evidence_level="direct")
            limited_snippets = [(name, d) for name, d in
                                [("all bots", d) for d in generic_directives] + scoped_directives
                                if has_directive(d, "nosnippet") or
                                re.search(r"max-snippet\s*:\s*0(?:\D|$)", d, re.I)]
            if limited_snippets:
                scopes = ", ".join(name for name, _ in limited_snippets)
                add("GEO-SNIPPET-RESTRICTION", "Директива ограничивает использование фрагментов текста",
                    f"Ограничение для: {scopes}. Это может влиять на возможности "
                    "использования страницы соответствующими поисковыми системами.",
                    "medium", page, "needs_review", "high",
                    "Подтвердить необходимость ограничения для каждого бота.",
                    [GOOGLE_AI, GOOGLE_ROBOTS], "HTTP+DOM", evidence_level="direct")
            if not page.title:
                add("GEO-TITLE", "Отсутствует title", "В исходном HTML не найден <title>; JavaScript может изменить документ после загрузки.",
                    "medium", page, "observation", "high", "Добавить точный, уникальный заголовок, согласованный с темой страницы.",
                    evidence_level="direct")
            elif page.title.casefold().strip() in seen_titles:
                add("GEO-DUP-TITLE", "Повторяющийся title",
                    f"Title уже найден на {seen_titles[page.title.casefold().strip()]}; повтор может быть обоснован шаблоном или каноникализацией.",
                    "low", page, "needs_review", "high", "Сравнить назначение страниц и канонические URL.")
            else:
                seen_titles[page.title.casefold().strip()] = page.url
            if not page.description:
                add("GEO-DESCRIPTION", "В HTML отсутствует meta description",
                    "Описание может быть полезным для сниппета, но это не обязательное условие индексации или AI-ответов.",
                    "low", page, "observation", "high", "Подготовить осмысленное описание, если это оправдано для целевой страницы.",
                    evidence_level="direct")
            if not page.h1:
                rendered = next((item for item in snapshot.browser_evidence
                                 if str(item.get("url", "")).rstrip("/") == page.url.rstrip("/")), None)
                if rendered and int(rendered.get("rendered_h1_count", 0)) > 0:
                    add("GEO-H1-JS", "H1 появляется после JavaScript",
                        "В исходном HTML H1 отсутствует, но в разрешённой браузерной проверке он обнаружен. "
                        "Это не доказывает проблему индексации; проверьте требования поисковой платформы.",
                        "low", page, "needs_review", "high", "Проверить серверный HTML, рендеринг и Search Console / Вебмастер.",
                        evidence_level="direct")
                else:
                    add("GEO-H1", "В исходном HTML отсутствует H1",
                        "Отсутствует заголовок H1 в статическом HTML; сам по себе этот признак не подтверждает низкую видимость.",
                        "low", page, "observation", "high", "Проверить структуру отрисованной страницы.", evidence_level="direct")
            if page.canonical and page.canonical.rstrip("/") != page.url.rstrip("/"):
                external = (urlparse(page.canonical).hostname != urlparse(page.url).hostname)
                add("GEO-CANONICAL", "Canonical указывает на иной URL",
                    f"canonical: {page.canonical}. " + ("Цель на другом хосте." if external else "Может быть нормальной каноникализацией варианта страницы."),
                    "medium" if external else "low", page, "needs_review", "high",
                    "Проверить целевую страницу, индексацию, редиректы и предполагаемую каноникализацию.",
                    evidence_level="direct")
            if "INVALID_JSON_LD" in page.structured_data:
                add("GEO-SCHEMA-INVALID", "Синтаксическая ошибка JSON-LD",
                    "Как минимум один блок application/ld+json не удалось разобрать как JSON. "
                    "Наличие корректного JSON-LD не гарантирует rich result или цитирование ИИ.",
                    "medium", page, "observation", "high", "Проверить блок в валидаторе и привести данные в соответствие видимому содержимому.",
                    [GOOGLE_SCHEMA], evidence_level="direct")
            else:
                types_found = set()
                for item in page.structured_data:
                    if isinstance(item, dict):
                        t = item.get("@type")
                        if isinstance(t, str):
                            types_found.add(t)
                        elif isinstance(t, list):
                            types_found.update(str(x) for x in t)
                expected = {"Organization", "WebSite", "Article", "FAQPage", "Product", "BreadcrumbList"}
                missing = expected - types_found
                if missing and len(page.text) > 200:
                    add("GEO-SCHEMA-TYPES", "Не обнаружены распространённые типы schema.org",
                        f"На странице не найдены типы: {', '.join(sorted(missing))}. "
                        "Это не ошибка и не гарантия отсутствия rich results. Наличие подходящей разметки может помочь поисковым системам и AI-системам.",
                        "info", page, "observation", "medium",
                        "Рассмотреть добавление релевантных типов schema.org (Organization, Article, FAQPage и т.д.) при соответствии содержимому.",
                        [GOOGLE_SCHEMA], evidence_level="indicative")
            if len(page.text.strip()) < 130 and page.scripts:
                add("GEO-RENDER-REVIEW", "Нужна проверка отрисованного содержимого",
                    "В статическом HTML очень мало видимого текста и есть JS-скрипты. Возможно, основное содержимое появляется после рендеринга.",
                    "low", page, "needs_review", "low", "Сравнить initial HTML с браузерным DOM и инструментом проверки URL у поисковика.")

        if self.queries:
            for query in self.queries:
                q_terms = terms(query)
                if not q_terms:
                    continue
                coverage = []
                for p in snapshot.pages:
                    tokens = terms(" ".join([p.title, *p.h1, *p.h2, p.text[:30000]]))
                    coverage.append((len(q_terms & tokens), p))
                best_score, best_page = max(coverage, key=lambda pair: pair[0])
                if best_score == 0:
                    add("GEO-QUERY-COVERAGE", "Целевой запрос не представлен в обнаруженном тексте",
                        f"Запрос: «{query}». Лексические совпадения с исследованными страницами не обнаружены. "
                        "Это слабая эвристика и не измерение релевантности или поискового спроса.",
                        "low", best_page, "needs_review", "low",
                        "Проверить целевую страницу, интент и соответствие ответа на вопрос; при необходимости подключить редактора.",
                        [YANDEX_GUIDE, GOOGLE], context=query)

        for evidence in snapshot.browser_evidence:
            page = pages_by_url.get(str(evidence.get("url", "")).rstrip("/"))
            if not page:
                continue
            rendered_length = int(evidence.get("rendered_text_chars", 0))
            if len(page.text) < 130 and rendered_length >= 500:
                add("GEO-RENDER-DIFF", "Основной текст зависит от исполнения JavaScript",
                    f"Статический HTML содержит {len(page.text)} символов, браузерный DOM — около {rendered_length}. "
                    "Это не доказывает, что Google или Яндекс не видят контент.",
                    "medium", page, "needs_review", "high",
                    "Проверить серверный рендеринг и представление страницы через инструменты поисковых систем.",
                    [GOOGLE_AI, "https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics"],
                    "browser", evidence_level="direct")

        add("GEO-AI-VISIBILITY", "Фактическая видимость в ответах ИИ не измерена",
            "Аудит HTML не измеряет цитирования в Алисе AI, Google AI или ChatGPT. Для Алисы AI доступен отчёт Вебмастера "
            "для подтверждённых сайтов; методика оценки должна учитывать изменения набора запросов и период измерения.",
            "info", snapshot.final_url, "not_tested", "high",
            "Подключить Вебмастер, согласовать целевые запросы и базовый период мониторинга.",
            [YANDEX, GOOGLE_AI], "external_configuration", evidence_level="insufficient")
        return findings
