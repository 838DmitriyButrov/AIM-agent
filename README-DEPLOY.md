# AIM Agent - deployment handoff

This is the GitHub-ready source of Site Audit Agents v0.2.1, including LEGAL and GEO/SEO agents.
The UX/UI agent remains a placeholder.

- Setup: README.md
- Production limitations: docs/SECURITY.md
- Railway deployment checklist: docs/RAILWAY_DEPLOY.md
- Dockerfile: Python 3.12 + FastAPI, private staging only
- CI: .github/workflows/tests.yml

Do not publish the Python API openly. GitHub's permission to Railway to pull a repository is NOT permission for an external assistant to push changes.
