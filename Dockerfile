FROM denoland/deno:bin-2.9.4 AS deno

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DENO_DIR=/tmp/deno-cache

WORKDIR /app

COPY --from=deno /deno /usr/local/bin/deno

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && useradd --create-home --uid 10001 app \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"]
CMD ["uvicorn", "media_download_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
