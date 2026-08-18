FROM denoland/deno:bin-2.9.4 AS deno

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DENO_DIR=/tmp/deno-cache

WORKDIR /app

COPY --from=deno /deno /usr/local/bin/deno

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "media_download_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
