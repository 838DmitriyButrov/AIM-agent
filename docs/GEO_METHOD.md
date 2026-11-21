# GEO/SEO Agent — методика v0.2, AI Search first

**Цель:** выявить технические барьеры и темы для содержательного улучшения поисковой пригодности сайта. **Не** предсказывать цитируемость или позиции.

1. **Доступ:** robots.txt (отдельно проверяются Googlebot/YandexBot), HTTP/X-Robots-Tag, meta robots и отдельные теги для ботов, ограничения на snippets, canonical. `robots.txt` — механизм crawl control, а не гарантия деиндексации.
2. **Содержимое:** title, заголовки, признаки пустого initial HTML, сравнение с DOM после рендеринга при опциональном Playwright. Краткость текста без контекста не считаем ошибкой.
3. **Карта сайта:** отличать HTTP 200 HTML от XML sitemap, учитывать нестандартный URL в `Sitemap:`; содержимое объявленных карт пока не верифицируется.
4. **Структурированные данные:** проверять синтаксически неверный JSON-LD, но не ругать отсутствие JSON-LD на каждой странице. Разметка не гарантирует генеративную выдачу.
5. **Соответствие запросам:** только явно заданные целевые вопросы. Детерминированный лексический ноль = низкоуверенное `needs_review`, а не SEO-вердикт; смысловую глубину можно оценивать LLM с ручной верификацией.
6. **Фактическая AI-видимость:** `not_tested`, пока не подключены официальные отчёты или контролируемые внешние измерения. Отчёт Яндекс Вебмастера по Алисе AI требует подтверждённых прав.

## Лучшие практики

- У Google нет особой обязательной schema.org/`llms.txt` для AI Overviews или AI Mode. Применяйте общие принципы поисковой доступности, полезности и достоверности информации.
- У Яндекса ответы Алисы AI связаны с качеством обычных результатов поиска; доля цитирований SoV зависит от набора запросов и периода.
- Не подменять редактуру контента массовой генерацией бесполезных текстов и фиктивных E-E-A-T маркеров.

## Источники

- [Google AI optimization](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
- [Google AI features](https://developers.google.com/search/docs/appearance/ai-features)
- [Google robots meta](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)
- [Google structured data general guidelines](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)
- [Google JavaScript SEO](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
- [Яндекс: что влияет на попадание в ИИ-ответы](https://yandex.ru/support/webmaster/ru/epos)
- [Яндекс Вебмастер: видимость сайта в Алисе AI](https://yandex.ru/support/webmaster/ru/service/alice-answers)
