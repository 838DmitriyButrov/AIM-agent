"""Compare observed organic search results with the HTML of the same URL."""
from __future__ import annotations

import base64
import json
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx
from pydantic import AnyHttpUrl, AwareDatetime, BaseModel, Field, TypeAdapter

from .finding_utils import issue_id
from .models import Evidence, Finding, SiteSnapshot

YANDEX_SEARCH = "https://searchapi.api.cloud.yandex.net/v2/web/search"
YANDEX_DOC = "https://aistudio.yandex.ru/en/docs/search-api/api-ref/WebSearch/search"
GOOGLE_TITLE = "https://developers.google.com/search/docs/appearance/title-link"
GOOGLE_SNIPPET = "https://developers.google.com/search/docs/appearance/snippet"


class SearchResult(BaseModel):
    url: AnyHttpUrl
    position: int = Field(ge=1, le=100)
    title: str = Field(default="", max_length=1000)
    snippet: str = Field(default="", max_length=2000)


class SearchSnapshot(BaseModel):
    engine: str = Field(min_length=1, max_length=60)
    query: str = Field(min_length=1, max_length=400)
    region: str = Field(min_length=1, max_length=100)
    observed_at: AwareDatetime
    source: str = Field(min_length=1, max_length=120)
    results: list[SearchResult] = Field(max_length=100)


def read_search_snapshots(path: Path) -> list[SearchSnapshot]:
    with path.open("rb") as file:
        data = file.read(1_000_001)
    if len(data) > 1_000_000:
        raise ValueError("SERP-файл должен быть не больше 1 МБ.")
    snapshots = TypeAdapter(list[SearchSnapshot]).validate_json(data)
    if not 1 <= len(snapshots) <= 20:
        raise ValueError("SERP-файл должен содержать от 1 до 20 снимков выдачи.")
    return snapshots


def yandex_snapshots(queries: list[str], region: str) -> list[SearchSnapshot]:
    key = os.getenv("YANDEX_SEARCH_API_KEY", "").strip()
    folder = os.getenv("YANDEX_SEARCH_FOLDER_ID", "").strip()
    if not key or not folder:
        raise ValueError("Укажите YANDEX_SEARCH_API_KEY и YANDEX_SEARCH_FOLDER_ID в окружении.")
    queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))
    if not 1 <= len(queries) <= 5 or any(len(query) > 400 for query in queries):
        raise ValueError("Для Яндекс Search API задайте от 1 до 5 запросов длиной до 400 символов.")
    if not region.isascii() or not region.isdecimal() or len(region) > 12:
        raise ValueError("Для Яндекса нужен числовой ID региона, например 213 для Москвы.")
    with httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as client:
        return [_yandex_snapshot(client, key, folder, query, region) for query in queries]


def _yandex_snapshot(client: httpx.Client, key: str, folder: str, query: str, region: str) -> SearchSnapshot:
    body = {
        "query": {"searchType": "SEARCH_TYPE_RU", "queryText": query, "page": "0"},
        "groupSpec": {"groupMode": "GROUP_MODE_FLAT", "groupsOnPage": "10", "docsInGroup": "1"},
        "region": region, "folderId": folder, "responseFormat": "FORMAT_XML",
    }
    try:
        with client.stream("POST", YANDEX_SEARCH, headers={"Authorization": f"Api-Key {key}"}, json=body) as response:
            if response.status_code != 200:
                raise ValueError(f"Яндекс Search API вернул HTTP {response.status_code}. Выдача не получена.")
            data = bytearray()
            for chunk in response.iter_bytes(chunk_size=65536):
                data.extend(chunk)
                if len(data) > 1_000_000:
                    raise ValueError("Ответ Яндекс Search API превышает 1 МБ.")
    except httpx.RequestError:
        raise ValueError("Не удалось подключиться к Яндекс Search API. Выдача не получена.") from None
    try:
        xml = base64.b64decode(json.loads(data)["rawData"], validate=True)
        # API XML has no DTD. Reject declarations before passing data to the XML parser.
        xml_text = xml.decode("utf-8-sig")
        if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
            raise ValueError
        root = ElementTree.fromstring(xml_text)
    except (ElementTree.ParseError, KeyError, TypeError, ValueError):
        raise ValueError("Яндекс Search API вернул неподдерживаемый XML-ответ.") from None
    if root.find(".//error") is not None or root.find(".//response") is None:
        raise ValueError("Яндекс Search API не предоставил результаты запроса.")
    results = []
    for position, doc in enumerate(root.findall(".//group/doc")[:10], 1):
        title = doc.find("title")
        passages = doc.findall("./passages/passage")
        results.append(SearchResult(
            url=doc.findtext("url", ""), position=position,
            title="".join(title.itertext())[:1000] if title is not None else "",
            snippet=" … ".join("".join(passage.itertext()) for passage in passages)[:2000],
        ))
    return SearchSnapshot(engine="Яндекс", query=query, region=region, observed_at=datetime.now(timezone.utc),
                          source="Яндекс Search API (XML, заголовок и фрагменты)", results=results)


def _url_key(url: str) -> tuple:
    parsed = urlsplit(url)
    return parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split()).casefold()


def compare_search(snapshot: SiteSnapshot, observations: list[SearchSnapshot]) -> tuple[list[Finding], dict[str, int]]:
    pages = {_url_key(page.url): page for page in snapshot.pages}
    stats = {"serp_queries_checked": len(observations), "serp_urls_matched": 0, "serp_fields_compared": 0}
    findings = []
    for observation in observations:
        matched = [result for result in observation.results if _url_key(str(result.url)) in pages]
        stats["serp_urls_matched"] += len(matched)
        for result in matched:
            page = pages[_url_key(str(result.url))]
            source = f"{observation.engine}, запрос «{observation.query}», регион {observation.region}, {observation.observed_at.isoformat(timespec='seconds')}. Источник: {observation.source}. Номер результата в снимке: {result.position}."
            is_yandex_api = observation.source.startswith("Яндекс Search API")
            for field, name, html_value, search_value, guide, action in (
                ("TITLE", "Заголовок", page.title, result.title, GOOGLE_TITLE,
                 "Согласовать title, H1 и главный заголовок страницы. В начало вынести товар или категорию и уточнение, которое отвечает на этот запрос. Затем повторить замер."),
                ("DESCRIPTION", "Описание", page.description, result.snippet, GOOGLE_SNIPPET,
                 "Проверить, отвечает ли meta description на запрос, и вынести полезные покупателю сведения в описание и видимый текст. Поисковик может брать фрагменты со страницы."),
            ):
                if not search_value.strip():
                    continue
                stats["serp_fields_compared"] += 1
                if field == "DESCRIPTION" and is_yandex_api:
                    name = "Фрагменты Яндекс Search API"
                original = _normalize(html_value)
                observed = _normalize(search_value)
                differs = original != observed
                visible_prefix = observed.removesuffix("...").removesuffix("…").rstrip()
                truncated = differs and bool(visible_prefix) and visible_prefix != observed and original.startswith(visible_prefix)
                if truncated:
                    action = "Вынести название и важные для запроса уточнения в начало текста. Затем проверить, что видно в выдаче на телефоне и компьютере."
                explanation = f"{source}\n\nВ HTML: {html_value.strip() or 'тег пуст или отсутствует'}.\n\nВ источнике выдачи: {search_value.strip()}."
                key = f"{observation.engine}|{observation.query}|{observation.region}|{observation.observed_at.isoformat()}|{result.position}"
                rule = "GEO-SERP-TRUNCATED" if truncated else f"GEO-SERP-{field}" if differs else "GEO-SERP-MATCH"
                comparison = "показан сокращённо" if truncated else "отличается от HTML" if differs else "совпадает с HTML"
                findings.append(Finding(
                    id=issue_id("geo", rule, page.url, f"{field}|{key}"),
                    agent="geo", rule_id=rule,
                    title=f"{name}: {comparison}",
                    explanation=explanation, severity="low" if differs else "info",
                    status="needs_review" if differs else "observation", confidence="high",
                    applicability="conditional", evidence_level="direct",
                    evidence=[Evidence(page=page.url, kind="search_result", detail=source[:600])],
                    references=[YANDEX_DOC] if is_yandex_api else [guide] if observation.engine.casefold() == "google" else [],
                    action=action if differs else "Сохранить как точку сравнения для следующих замеров.",
                    needs_human_review=differs,
                ))
        if not any(result.title.strip() or result.snippet.strip() for result in matched):
            rule = "GEO-SERP-NO-COMPARISON"
            findings.append(Finding(
                id=issue_id("geo", rule, snapshot.input_url,
                            f"{observation.engine}|{observation.query}|{observation.region}|{observation.observed_at.isoformat()}"),
                agent="geo", rule_id=rule, title=f"Выдача по запросу «{observation.query}»",
                explanation=f"{observation.engine}, регион {observation.region}. В снимке нет пары из доступного текста результата и HTML того же URL.",
                severity="info", status="not_tested", confidence="high", evidence_level="insufficient",
                action=f"{observation.engine}, регион {observation.region}, {observation.observed_at.isoformat(timespec='seconds')}. Сверить URL из снимка с проверенными страницами. Статус индексации по этому результату установить нельзя.",
            ))
    return findings, stats
