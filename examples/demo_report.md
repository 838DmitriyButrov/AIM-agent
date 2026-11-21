# Аудит сайта

**URL:** https://example.org/demo
**Дата (UTC):** 2026-11-21T21:47:07.908792+00:00
**Агенты:** LEGAL, GEO
**Страниц исследовано:** 1
**Потенциальных рисков:** 1
**На ручной проверке:** 3
**Не проверено:** 4

## Охват проверки

- sampled_pages: 1
- max_pages_requested: 1
- crawl_limit_reached: False
- browser_pages_probed: 0
- confirmed_ai_search_visibility: False
- verified_legal_compliance: False

## Находки

### 1. В месте сбора данных не обнаружена ссылка на политику
**LEGAL · LEGAL-PD-POLICY · needs_review · medium · уверенность: medium**
**Применимость:** conditional; **уровень доказательств:** indicative

Форма потенциально собирает ПДн, но в исходном HTML этой страницы не обнаружена ссылка на политику. Ссылка может добавляться через JavaScript либо документ может быть доступен иным способом; это не подтверждённое нарушение.

**Рекомендация:** Проверить фактическую доступность политики на странице сбора данных, включая отрисованную версию.

- Доказательство (DOM): https://example.org/demo — Форма потенциально собирает ПДн, но в исходном HTML этой страницы не обнаружена ссылка на политику. Ссылка может добавляться через JavaScript либо документ может быть доступен иным способом; это не подтверждённое нарушение.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://www.consultant.ru/document/cons_doc_LAW_61801/eeeebe22bf738fd65bb66b95cc278911ae2525ee/

### 2. Заранее отмеченное согласие в исходном HTML
**LEGAL · LEGAL-PD-CONSENT · potential_risk · medium · уверенность: high**
**Применимость:** conditional; **уровень доказательств:** direct

В форме с потенциальными ПДн обнаружен чекбокс согласия с HTML-атрибутом checked. Фактическое состояние после загрузки JS и правовое основание обработки ещё не проверены.

**Рекомендация:** Проверить состояние в браузере и основание обработки; при согласии обеспечить самостоятельное волеизъявление.

- Доказательство (DOM): https://example.org/demo — В форме с потенциальными ПДн обнаружен чекбокс согласия с HTML-атрибутом checked. Фактическое состояние после загрузки JS и правовое основание обработки ещё не проверены.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://www.consultant.ru/document/Cons_doc_LAW_61801/6c94959bc017ac80140621762d2ac59f6006b08c/

### 3. Согласие на ПДн может быть объединено с другим действием
**LEGAL · LEGAL-PD-CONSENT · needs_review · medium · уверенность: medium**
**Применимость:** conditional; **уровень доказательств:** indicative

Текст чекбокса: Согласен на обработку персональных данных и с условиями оферты. Отдельность согласия зависит от того, что пользователь фактически подписывает/подтверждает.

**Рекомендация:** Проверить требования статьи 9, основание обработки и при необходимости отделить согласие от остальных документов.

- Доказательство (DOM): https://example.org/demo — Текст чекбокса: Согласен на обработку персональных данных и с условиями оферты. Отдельность согласия зависит от того, что пользователь фактически подписывает/подтверждает.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://www.consultant.ru/document/Cons_doc_LAW_61801/6c94959bc017ac80140621762d2ac59f6006b08c/

### 4. Локализация и инфраструктура ПДн
**LEGAL · LEGAL-PD-LOCALIZATION · not_tested · info · уверенность: high**
**Применимость:** unknown; **уровень доказательств:** insufficient

Автоматический публичный обход не устанавливает выполнение требования. Data flow map, storage location and processing infrastructure.

**Рекомендация:** Проверить область применимости и собрать документы от оператора сайта.

- Источник: https://www.consultant.ru/document/cons_doc_LAW_61801/cbf4e15b7c330f9372e876cdf2bc928bad7950ef/

### 5. Внутренние меры защиты ПДн
**LEGAL · LEGAL-PD-SECURITY · not_tested · info · уверенность: high**
**Применимость:** unknown; **уровень доказательств:** insufficient

Автоматический публичный обход не устанавливает выполнение требования. Security controls, access policies, data retention and incident procedures.

**Рекомендация:** Проверить область применимости и собрать документы от оператора сайта.

- Источник: https://www.consultant.ru/document/cons_doc_LAW_61801/ca9e5658710519f09ab2fdb8196fcb3eb024a051/

### 6. Уведомление оператора в Роскомнадзор
**LEGAL · LEGAL-PD-RKN · not_tested · info · уверенность: high**
**Применимость:** unknown; **уровень доказательств:** insufficient

Автоматический публичный обход не устанавливает выполнение требования. Resolve legal entity and current status in RKN registry, review exceptions.

**Рекомендация:** Проверить область применимости и собрать документы от оператора сайта.

- Источник: https://www.consultant.ru/document/cons_doc_LAW_61801/

### 7. Не обнаружена карта сайта по стандартному адресу или в robots.txt
**GEO · GEO-SITEMAP · observation · low · уверенность: high**
**Применимость:** conditional; **уровень доказательств:** direct

По адресу /sitemap.xml не найдена XML-карта; в robots.txt нет директив Sitemap. Карта сайта не обязательна и может быть доступна по другому адресу.

**Рекомендация:** При необходимости указать XML sitemap в robots.txt.

- Доказательство (DOM): https://example.org/demo — По адресу /sitemap.xml не найдена XML-карта; в robots.txt нет директив Sitemap. Карта сайта не обязательна и может быть доступна по другому адресу.
- Источник: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Источник: https://yandex.ru/support/webmaster/ru/epos

### 8. Обнаружена директива noindex
**GEO · GEO-NOINDEX · observation · medium · уверенность: high**
**Применимость:** conditional; **уровень доказательств:** direct

meta robots / X-Robots-Tag: noindex. Может быть намеренным для служебных страниц; не является подтверждением отсутствия в индексе.

**Рекомендация:** Проверить предназначение страницы и индексирование в Вебмастере / Search Console.

- Доказательство (HTTP+DOM): https://example.org/demo — meta robots / X-Robots-Tag: noindex. Может быть намеренным для служебных страниц; не является подтверждением отсутствия в индексе.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag

### 9. Отсутствует title
**GEO · GEO-TITLE · observation · medium · уверенность: high**
**Применимость:** conditional; **уровень доказательств:** direct

В исходном HTML не найден <title>; JavaScript может изменить документ после загрузки.

**Рекомендация:** Добавить точный, уникальный заголовок, согласованный с темой страницы.

- Доказательство (DOM): https://example.org/demo — В исходном HTML не найден <title>; JavaScript может изменить документ после загрузки.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Источник: https://yandex.ru/support/webmaster/ru/epos

### 10. В HTML отсутствует meta description
**GEO · GEO-DESCRIPTION · observation · low · уверенность: high**
**Применимость:** conditional; **уровень доказательств:** direct

Описание может быть полезным для сниппета, но это не обязательное условие индексации или AI-ответов.

**Рекомендация:** Подготовить осмысленное описание, если это оправдано для целевой страницы.

- Доказательство (DOM): https://example.org/demo — Описание может быть полезным для сниппета, но это не обязательное условие индексации или AI-ответов.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Источник: https://yandex.ru/support/webmaster/ru/epos

### 11. В исходном HTML отсутствует H1
**GEO · GEO-H1 · observation · low · уверенность: high**
**Применимость:** conditional; **уровень доказательств:** direct

Отсутствует заголовок H1 в статическом HTML; сам по себе этот признак не подтверждает низкую видимость.

**Рекомендация:** Проверить структуру отрисованной страницы.

- Доказательство (DOM): https://example.org/demo — Отсутствует заголовок H1 в статическом HTML; сам по себе этот признак не подтверждает низкую видимость.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Источник: https://yandex.ru/support/webmaster/ru/epos

### 12. Синтаксическая ошибка JSON-LD
**GEO · GEO-SCHEMA-INVALID · observation · medium · уверенность: high**
**Применимость:** conditional; **уровень доказательств:** direct

Как минимум один блок application/ld+json не удалось разобрать как JSON. Наличие корректного JSON-LD не гарантирует rich result или цитирование ИИ.

**Рекомендация:** Проверить блок в валидаторе и привести данные в соответствие видимому содержимому.

- Доказательство (DOM): https://example.org/demo — Как минимум один блок application/ld+json не удалось разобрать как JSON. Наличие корректного JSON-LD не гарантирует rich result или цитирование ИИ.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://developers.google.com/search/docs/appearance/structured-data/sd-policies

### 13. Целевой запрос не представлен в обнаруженном тексте
**GEO · GEO-QUERY-COVERAGE · needs_review · low · уверенность: low**
**Применимость:** conditional; **уровень доказательств:** indicative

Запрос: «Как оформить заказ?». Лексические совпадения с исследованными страницами не обнаружены. Это слабая эвристика и не измерение релевантности или поискового спроса.

**Рекомендация:** Проверить целевую страницу, интент и соответствие ответа на вопрос; при необходимости подключить редактора.

- Доказательство (DOM): https://example.org/demo — Запрос: «Как оформить заказ?». Лексические совпадения с исследованными страницами не обнаружены. Это слабая эвристика и не измерение релевантности или поискового спроса.
  - SHA-256 исходного HTML: `5b5cb08bc075fb8c7995ede5d5ad51647efe7bba3924f667ee63c2717bfaa3fa`
- Источник: https://yandex.ru/support/webmaster/ru/epos
- Источник: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide

### 14. Фактическая видимость в ответах ИИ не измерена
**GEO · GEO-AI-VISIBILITY · not_tested · info · уверенность: high**
**Применимость:** conditional; **уровень доказательств:** insufficient

Аудит HTML не измеряет цитирования в Алисе AI, Google AI или ChatGPT. Для Алисы AI доступен отчёт Вебмастера для подтверждённых сайтов; методика оценки должна учитывать изменения набора запросов и период измерения.

**Рекомендация:** Подключить Вебмастер, согласовать целевые запросы и базовый период мониторинга.

- Доказательство (external_configuration): https://example.org/demo — Аудит HTML не измеряет цитирования в Алисе AI, Google AI или ChatGPT. Для Алисы AI доступен отчёт Вебмастера для подтверждённых сайтов; методика оценки должна учитывать изменения набора запросов и период измерения.
- Источник: https://yandex.ru/support/webmaster/ru/service/alice-answers
- Источник: https://developers.google.com/search/docs/appearance/ai-features

## Ограничения

- Это демонстрационный отчёт на вымышленном HTML, а не юридическое заключение.
- Нахождение сигнала не означает установленного нарушения или проблем с индексированием.
