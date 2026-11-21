# Исследование практик и архитектурные решения — 6 проходов

**Срез:** 22.11.2026. **Результат:** изменения в v0.2.0. Указанные сервисы исследованы по опубликованным методологиям, без самостоятельного тестирования их закрытых движков. Не следует считать это доказательством их фактической точности.

## Проход 1. Рынок аудиторских инструментов

**Примеры:** [Sitebulb hints](https://support.sitebulb.com/en/articles/9854034-about-sitebulb-hints), [Sitebulb technical audit checklist](https://sitebulb.com/technical-seo/audit-checklist/), [Screaming Frog JavaScript crawling](https://www.screamingfrog.co.uk/seo-spider/tutorials/crawl-javascript-seo/), [OneTrust scan results](https://docs.onetrust.com/en/consent--preferences/cookie-consent/scanning-a-website-categorizing-and-maintaining-cookies/scanning-and-scan-results-best-practices-and-troubleshooting).

**Вывод:** полезные инструменты не просто перечисляют отсутствующие теги: они дают контекст, приоритет, проверяемый след и способы повторного анализа. Не каждый hint равнозначен проблеме бизнеса.

**В v0.2:** стабильные ID, уровень доказательств, применимость, SHA-256 исходной HTML-страницы, удаление шумного сигнала «нет JSON-LD». **Далее:** группировка находок по шаблонам и бизнес-приоритет, сравнение релизов.

## Проход 2. LEGAL: условия применимости перед квалификацией

**Источники:** [152-ФЗ ст. 9](https://www.consultant.ru/document/cons_doc_LAW_61801/6c94959bc017ac80140621762d2ac59f6006b08c/), [152-ФЗ ст. 18.1](https://www.consultant.ru/document/cons_doc_LAW_61801/eeeebe22bf738fd65bb66b95cc278911ae2525ee/), [152-ФЗ Минтруд](https://mintrud.gov.ru/docs/laws/130).

**Вывод:** найденное поле телефона не устанавливает правовое основание обработки; ссылка на политику не доказывает её содержания; согласие не требуется при всякой обработке. Ошибкой будет автоматически объявлять отсутствие чекбокса нарушением.

**В v0.2:** для каждого элемента формы: `signal → normative gate → evidence status → expert task`. Учитывается ссылка на политику именно на странице сбора данных, но непроверенная ссылка остаётся `not_tested`. Только заведомо условные риски, без «штрафов» и вердиктов. **Далее:** загрузка документов и верификация полного текста, правовые версии и реальные дела с официальными реквизитами (сейчас проверенных дел в реестре нет).

## Проход 3. Техническая поисковая доступность

**Источники:** [Google robots/X-Robots](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag), [Google JavaScript SEO](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics), [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html), [Google structured data](https://developers.google.com/search/docs/appearance/structured-data/sd-policies).

**Вывод:** необходимо проверять фактически полученный HTTP, meta robots по ботам, `nosnippet`, настройки роботов и сравнение initial HTML с rendered DOM. Наличие JSON-LD само по себе не гарантирует AI-видимость.

**В v0.2:** X-Robots-Tag, googlebot/YandexBot meta, отдельные robots-проверки для ботов, различение `noindex` и блокировки `robots.txt`, проверка XML-формата sitemap (а не только HTTP 200), разница initial/rendered text в opt-in браузере.

## Проход 4. GEO / AI search: никакого выдуманного ранжирования

**Источники:** [Google AI optimization guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide), [Google AI features](https://developers.google.com/search/docs/appearance/ai-features), [Яндекс: принципы попадания в AI](https://yandex.ru/support/webmaster/ru/epos), [Яндекс: видимость в Алисе AI](https://yandex.ru/support/webmaster/ru/service/alice-answers).

**Вывод:** нет универсальной обязательной «GEO-разметки». Первичны индексируемость, точность и полезность содержания, поисковое соответствие намерению пользователя. Показатели видимости берут из подтверждённой поисковой аналитики, а не прогнозируют из HTML.

**В v0.2:** низкоуверенная эвристика покрытия только **переданных клиентом** целевых запросов. Реальная видимость всегда `not_tested` без подключённых данных. Не создаётся искусственная оценка вроде «AI-ready 93%».

## Проход 5. Безопасность и минимизация данных

**Источники:** [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html), [OneTrust consent scanning](https://docs.onetrust.com/en/consent--preferences/cookie-consent/scanning-a-website-categorizing-and-maintaining-cookies/scanning-a-website).

**Вывод:** простая проверка DNS до сетевого запроса не закрывает DNS rebinding. Безопасность достигается эшелонированными ограничениями, в том числе на сетевом уровне. Скриншоты и значения cookies/форм могут содержать персональные данные и требуют особого режима обращения.

**В v0.2:** только GET, ограничение хоста, robots.txt, числа страниц, длины ответа/времени, защита от известных GET-путей, минимизация полей (никаких cookie values/password/input values), явное предупреждение: **не публиковать API без сетевого egress firewall / proxy, блокирующего приватные адреса после DNS-резолва**. Браузер — по явному флагу и только на разрешённых сайтах. Это снижение риска, не сертификация безопасности.

## Проход 6. Качество и анти-ложноположительный дизайн

**Практика:** фиксированные сценарии с известным ожидаемым статусом, стабильность результатов между прогонами, отдельный слой доказательств, явный `not_tested`, экспертная разметка спорных случаев. Детерминированные правила должны быть независимо тестируемы без доступа к ИИ или сети.

**В v0.2:** тесты в `tests/`: корректный сайт без искусственных претензий; корректно разделённые согласия; комбинированное / prechecked согласие; policy по непрозрачному URL; `X-Robots-Tag`, bot-specific meta, `robots.txt` с разными правилами, пользовательские вопросы, JS-rendering, стабильные идентификаторы и отказ от хранения приватных полей. Начальная проверка v0.1: 9 тестов; v0.2: 29 тестов. Это **расширение покрытия тестов**, а не доказательство роста точности на реальных сайтах.

---

## Целевой алгоритм для следующего этапа

```
AUTHORIZATION + TARGET SCOPE
    ↓
BOUNDED FETCH (robots, safe methods, egress IP policy)
    ↓
FACTS (HTTP headers, initial HTML, optional rendered DOM, documents)
    ├── LEGAL: audience/operator → applicable rules → observed facts
    │          → evidence sufficiency → expert queue → decision
    └── GEO: fetchability → index eligibility → content/query fit
               → structured data relevance → verified platform visibility
    ↓
NORMALIZED FINDINGS (stable ID, source hash, evidence, reviewer status)
    ↓
PRIORITIZATION (legal urgency ≠ SEO opportunity; separate tracks)
    ↓
FIX + RERUN + REGRESSION + CLIENT SIGN-OFF
```

### Правило «безопасное утверждение»

| Ситуация | Допустимый статус | Запрещённый вывод |
|---|---|---|
| У HTML-формы нет найденной ссылки на политику | `needs_review` | «Сайт точно нарушает 152-ФЗ» |
| Политика найдена по ссылке, но документ не открыт | `not_tested` | «Требование выполнено» |
| Есть unchecked согласие | Обычно нет замечания | «Согласие юридически корректно» |
| `noindex` на странице | `observation` | «Сайт отсутствует в индексе» |
| `Disallow` для Googlebot | `observation` | «URL гарантированно отсутствует в Google» |
| Не найден JSON-LD | Отсутствие issue | «Нельзя попасть в AI-ответы» |
| Не подключён Яндекс Вебмастер | `not_tested` | «0% AI-видимости» |
| IP не в России | Нужна инфраструктурная проверка | «Нарушена локализация ПДн» |

## Что НЕ реализовано

- Юридическая верификация регистров и судебной практики, автоматическая квалификация нарушений.
- Многошаговые consent-сценарии «до/после согласия»; включение кнопок без авторизации небезопасно.
- Индексация поисковиком и фактическая видимость в Алисе AI / Google / ChatGPT.
- Полный анализ JavaScript на всём сайте (сейчас только opt-in первый URL).
- Production SSRF-сегментация, IP-pinning, RBAC, очереди, распределённое выполнение.
- Полноценный HTML template clustering, query-to-page mapping с настоящей статистикой спроса.

**Не использовать как заключение о соответствии законам или обещание получения позиций/цитирований в ИИ.**
