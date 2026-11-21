"""Evidence-first Russian legal triage. It never certifies statutory compliance."""
from __future__ import annotations
import json
import re
from pathlib import Path
from ..finding_utils import evidence_from_page, issue_id
from ..models import Finding, Page, SiteSnapshot

RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "legal_rules.json"
POLICY = re.compile(r"(политик[^.\n]{0,60}(персональн|конфиденц)|privacy[-_/ ]policy|обработк[^.\n]{0,40}персональн)", re.I)
CONSENT = re.compile(r"(согласи|согласен|consent).{0,140}(персональн|данных|privacy)|(персональн).{0,140}(согласи|согласен)", re.I)
PERSONAL = re.compile(r"(e-?mail|электронн|телефон|phone|имя|фамилия|first.?name|last.?name|fio|фио|адрес|address)", re.I)
COMBINED = re.compile(r"(оферт|услови|terms|договор|подписк|рассылк|реклам)", re.I)
CONSUMER = re.compile(r"(корзин|оформить заказ|добавить в корзину|купить сейчас|оплатить заказ|checkout)", re.I)
SELLER = re.compile(r"(инн\s*[:№]?\s*\d{10,12}|огрн\s*[:№]?\s*\d{13,15}|реквизит|сведения о продавце)", re.I)


def rules_by_id() -> dict:
    registry = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return {r["id"]: r for r in registry["rules"]}


def _finding(rule: dict, page: Page, key: str, title: str, explanation: str,
             severity: str, status: str, confidence: str, action: str,
             applicability: str = "conditional", evidence_level: str = "indicative",
             selector: str | None = None) -> Finding:
    return Finding(
        id=issue_id("legal", rule["id"], page.url, key), agent="legal", rule_id=rule["id"],
        title=title, explanation=explanation, severity=severity, status=status,
        confidence=confidence, applicability=applicability, evidence_level=evidence_level,
        evidence=[evidence_from_page(page, "DOM", explanation, selector)],
        references=[rule["source"]], action=action, needs_human_review=True,
    )


def _policy_links(page: Page) -> list[str]:
    return [url for url in page.document_links
            if POLICY.search(url + " " + page.document_link_labels.get(url, "")) or "privacy" in url.lower()]


def _personal(form) -> bool:
    return any(f["type"] in {"email", "tel"} or PERSONAL.search(f.get("name", "") + " " + f.get("label", ""))
               for f in form.fields)


class LegalAgent:
    name = "legal"

    def run(self, snapshot: SiteSnapshot) -> list[Finding]:
        if not snapshot.pages:
            return [Finding(id="LEGAL-NO-DATA", agent="legal", rule_id="NO-DATA", title="Аудит не проведён",
                explanation="Не получено HTML-страниц; правовые выводы невозможны.", severity="info", status="not_tested",
                confidence="high", evidence_level="insufficient", action="Проверить доступность сайта и права на тестирование.")]

        rules = rules_by_id()
        findings: list[Finding] = []
        scanned_urls = {p.url.rstrip("/") for p in snapshot.pages}
        personal_forms: list[tuple[Page, object, int]] = []
        for page in snapshot.pages:
            for form_index, form in enumerate(page.forms, 1):
                if _personal(form):
                    personal_forms.append((page, form, form_index))
                    # Law requires availability of the policy at pages where collection takes place.
                    # A site-wide link from another page is not enough evidence of page accessibility.
                    links_here = _policy_links(page)
                    if not links_here:
                        findings.append(_finding(rules["LEGAL-PD-POLICY"], page, f"form:{form_index}",
                            "В месте сбора данных не обнаружена ссылка на политику",
                            "Форма потенциально собирает ПДн, но в исходном HTML этой страницы не обнаружена ссылка на политику. "
                            "Ссылка может добавляться через JavaScript либо документ может быть доступен иным способом; это не подтверждённое нарушение.",
                            "medium", "needs_review", "medium",
                            "Проверить фактическую доступность политики на странице сбора данных, включая отрисованную версию.",
                            selector=f"form:nth-of-type({form_index})"))
                    elif not any(link.rstrip("/") in scanned_urls for link in links_here):
                        findings.append(_finding(rules["LEGAL-PD-POLICY"], page, f"unverified:{form_index}",
                            "Ссылка на политику найдена, но документ не проверен",
                            "В исходном HTML присутствует ссылка на политику; её содержимое и HTTP-доступность не подтверждены в этом обходе.",
                            "info", "not_tested", "high", "Открыть связанный документ и проверить актуальность и применимость.",
                            evidence_level="insufficient"))

                for cb_index, cb in enumerate(form.checkboxes, 1):
                    label = str(cb.get("label") or "")
                    if not _personal(form) or not CONSENT.search(label):
                        continue
                    if cb.get("checked"):
                        findings.append(_finding(rules["LEGAL-PD-CONSENT"], page, f"form:{form_index}:checkbox:{cb_index}:checked",
                            "Заранее отмеченное согласие в исходном HTML",
                            "В форме с потенциальными ПДн обнаружен чекбокс согласия с HTML-атрибутом checked. "
                            "Фактическое состояние после загрузки JS и правовое основание обработки ещё не проверены.",
                            "medium", "potential_risk", "high",
                            "Проверить состояние в браузере и основание обработки; при согласии обеспечить самостоятельное волеизъявление.",
                            evidence_level="direct", selector=f"form:nth-of-type({form_index}) input[type=checkbox]"))
                    if COMBINED.search(label):
                        findings.append(_finding(rules["LEGAL-PD-CONSENT"], page, f"form:{form_index}:checkbox:{cb_index}:combined",
                            "Согласие на ПДн может быть объединено с другим действием",
                            f"Текст чекбокса: {label[:160]}. Отдельность согласия зависит от того, что пользователь фактически подписывает/подтверждает.",
                            "medium", "needs_review", "medium",
                            "Проверить требования статьи 9, основание обработки и при необходимости отделить согласие от остальных документов.",
                            selector=f"form:nth-of-type({form_index}) input[type=checkbox]"))

        # A site-wide policy link is only an observation, NOT evidence of valid text.
        # Avoid 'missing policy' allegation when no personal-data form was found.
        consumer_pages = [p for p in snapshot.pages if CONSUMER.search(p.text[:20000])]
        if consumer_pages:
            has_seller_info = any(SELLER.search(p.text) for p in snapshot.pages)
            if not has_seller_info:
                page = consumer_pages[0]
                findings.append(_finding(rules["LEGAL-CONSUMER-INFO"], page, "seller-info",
                    "Сведения о продавце требуют дополнительной проверки",
                    "На выборке страниц найден сценарий покупки, но типовые реквизиты не обнаружены. Они могут находиться в оферте, PDF или другой странице.",
                    "medium", "needs_review", "low",
                    "Проверить B2C-применимость, сведения об исполнителе, оферту, порядок возврата и способы связи."))

        # Only contextual manual checks. The absence of checks in a scan is NOT compliance.
        def manual(rule_id: str, title: str, condition: bool):
            if not condition:
                return
            r = rules[rule_id]
            findings.append(Finding(
                id=issue_id("legal", rule_id, snapshot.final_url, "expert-gate"),
                agent="legal", rule_id=rule_id, title=title,
                explanation="Автоматический публичный обход не устанавливает выполнение требования. " + r["human_check"],
                severity="info", status="not_tested", confidence="high", applicability="unknown", evidence_level="insufficient",
                references=[r["source"]], action="Проверить область применимости и собрать документы от оператора сайта.",
                needs_human_review=True))

        data_collection = bool(personal_forms)
        manual("LEGAL-PD-LOCALIZATION", "Локализация и инфраструктура ПДн", data_collection)
        manual("LEGAL-PD-SECURITY", "Внутренние меры защиты ПДн", data_collection)
        manual("LEGAL-PD-RKN", "Уведомление оператора в Роскомнадзор", data_collection)
        manual("LEGAL-KKT", "Чеки и расчёты", bool(consumer_pages))
        manual("LEGAL-LANGUAGE", "Языковые требования в потребительских интерфейсах", bool(consumer_pages))
        manual("LEGAL-AD-MARKING", "Квалификация и маркировка интернет-рекламы",
               any(re.search(r"\bреклам\w*\b", p.text, re.I) for p in snapshot.pages))
        return findings
