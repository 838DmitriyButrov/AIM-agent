# Архитектура v0.2

```
CLI / localhost API
        |
    Orchestrator
        |
  Safe(ish) scope-limited crawler ── optional Playwright (first page)
        |
    SiteSnapshot (facts + source SHA-256 + crawl coverage)
        |
        +─ LEGAL agent ── versioned rules ── expert-review tasks
        |
        +─ GEO/SEO agent ── search eligibility + client queries
        |
        +─ UX agent [placeholder]
        |
   Findings (stable IDs, rule, applicability, evidence level, references)
        |
  JSON + Markdown reports
```

Улучшения v0.2: единый тип доказательства, стабильные ID по rule/page/context, хеш статического HTML, самодостаточный пакет с реестром правил, сверка HTTP X-Robots и HTML, bot-specific rules и sitemap declarations, условные LEGAL-gates, `coverage` и более точные статусы.

**Ограничения:** hash не обеспечивает доступ к оригинальному HTML. Доказательный архив и журнал изменений — отдельная задача. GEO сейчас технический аудит и эвристика query coverage, а не измерение упоминаний в конкретных ИИ. LEGAL — триаж, не юридический вердикт.
