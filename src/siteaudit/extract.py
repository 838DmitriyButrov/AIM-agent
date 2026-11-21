"""Static HTML facts. Form values and password fields are never saved."""
from __future__ import annotations
import hashlib
import json
import re
from urllib.parse import urljoin, urlparse, urldefrag
from bs4 import BeautifulSoup
from .models import Page, FormInfo

DOCUMENT_PATTERN = re.compile(r"(политик|согласи|персональн|конфиденциальн|privacy|оферт|условия|terms|возврат|return|реквизит)", re.I)


def parse_page(url: str, status_code: int, html: str, headers: dict[str, str] | None = None) -> Page:
    headers = {k.lower(): str(v) for k, v in (headers or {}).items()}
    soup = BeautifulSoup(html, "html.parser")
    source_sha256 = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta_description = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    desc = str(meta_description.get("content", "")) if meta_description else ""
    robots_meta = ""
    robots_by_agent = {}
    for m in soup.select("meta[name][content]"):
        name = str(m.get("name") or "").strip().lower()
        if name == "robots":
            robots_meta += (", " if robots_meta else "") + str(m.get("content"))
        if name in {"googlebot", "yandex", "yandexbot", "bingbot"}:
            robots_by_agent[name] = str(m.get("content"))
    canonical_tag = soup.find("link", attrs={"rel": lambda val: val and "canonical" in val})
    canonical = urljoin(url, canonical_tag.get("href")) if canonical_tag and canonical_tag.get("href") else None

    forms = []
    for form in soup.find_all("form"):
        fields: list[dict[str, str]] = []
        checks: list[dict[str, str | bool]] = []
        for field in form.find_all(["input", "textarea", "select"]):
            typ = (field.get("type") or field.name or "text").lower()
            fid = str(field.get("id") or "")
            label = ""
            if fid:
                match = soup.find("label", attrs={"for": fid})
                if match:
                    label = match.get_text(" ", strip=True)
            if not label and field.find_parent("label"):
                label = field.find_parent("label").get_text(" ", strip=True)
            item = {"type": typ, "name": str(field.get("name") or ""), "label": label[:250],
                    "required": str(field.has_attr("required"))}
            if typ == "checkbox":
                checks.append({**item, "checked": field.has_attr("checked")})
            elif typ not in {"hidden", "submit", "button", "reset", "file", "password"}:
                fields.append(item)
        forms.append(FormInfo(action=form.get("action"), fields=fields, checkboxes=checks))

    links, docs, doc_labels, doc_ref_labels = set(), set(), set(), {}
    site_host = urlparse(url).hostname
    for a in soup.select("a[href]"):
        href = str(a.get("href") or "")
        abs_url = urldefrag(urljoin(url, href))[0]
        parsed = urlparse(abs_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.hostname == site_host:
            links.add(abs_url)
        if DOCUMENT_PATTERN.search(f"{href} {a.get_text(' ', strip=True)}"):
            docs.add(abs_url)
            label_text = a.get_text(" ", strip=True)[:300]
            doc_labels.add(label_text)
            doc_ref_labels[abs_url] = label_text

    raw_data: list[dict | list | str] = []
    for s in soup.select('script[type="application/ld+json"]'):
        content = (s.string or s.get_text() or "").strip()
        try:
            raw_data.append(json.loads(content))
        except (ValueError, TypeError):
            raw_data.append("INVALID_JSON_LD")

    scripts = [urljoin(url, str(s.get("src"))) for s in soup.select("script[src]") if s.get("src")]
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()
    text = re.sub(r"\s+", " ", " ".join(soup.stripped_strings))[:70_000]
    return Page(
        url=url, status_code=status_code, title=title, description=desc,
        canonical=canonical, lang=str(soup.html.get("lang", "")) if soup.html else "",
        robots_meta=robots_meta, robots_meta_by_agent=robots_by_agent,
        x_robots_tag=headers.get("x-robots-tag", ""), content_type=headers.get("content-type", ""),
        h1=[h.get_text(" ", strip=True)[:300] for h in soup.find_all("h1")],
        h2=[h.get_text(" ", strip=True)[:300] for h in soup.find_all("h2")],
        text=text, internal_links=sorted(links), document_links=sorted(docs), document_labels=sorted(doc_labels),
        document_link_labels=doc_ref_labels,
        scripts=scripts, structured_data=raw_data, forms=forms,
        html_bytes=len(html.encode("utf-8", errors="replace")), source_sha256=source_sha256,
    )
