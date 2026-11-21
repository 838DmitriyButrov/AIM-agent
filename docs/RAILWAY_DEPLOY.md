# Railway deployment notes (private staging only)

This repo contains the original Python LEGAL and GEO audit agents. The separate Railway Function beta is **not** this runtime.

1. Connect the GitHub repo `838DmitriyButrov/AIM-agent` to the **site-audit-python** service in Railway.
2. Choose `main`; Railway will build the `Dockerfile`.
3. Do **not** generate a public domain for the Python service until egress-level SSRF isolation, authorization, per-tenant quotas, and audit permissions are independently tested.
4. The `/health` endpoint serves Railway's health check. `/scan` requires `AUDIT_TOKEN` and a strictly configured `AUDIT_ALLOWED_HOSTS` list. Set both through Railway variables, never in Git or chat.
5. This is an early product prototype, not a verified legal-compliance service. Review all legal findings before publication.

Example variables in Railway (set secure values in Railway UI):

- `AUDIT_TOKEN`: strong random 32+ character string.
- `AUDIT_ALLOWED_HOSTS`: `lenta.com,metro-cc.ru,www.auchan.ru`
- `PORT`: configured by Railway.

No persistent audit history is included in the Python prototype. Do not expose as production without a database, background worker, browser isolation, logs/evidence storage and rate limiting.
