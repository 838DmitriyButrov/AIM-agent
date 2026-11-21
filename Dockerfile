FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir '.[api]'
RUN useradd --system --uid 10001 audit
USER audit
EXPOSE 8000
CMD ["sh", "-c", "uvicorn siteaudit.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
