# Media Download Service

The local control plane returns `202/queued` immediately, then processes `queued → processing → ready/failed`. Reusing the same job ID with the same input is idempotent; reusing it for different input is rejected.

Metadata inspection may use Decodo through `INSPECT_PROXY` or the `DECODO_*` settings. Media transfer is direct by default. Proxy fallback is available only when `DOWNLOAD_PROXY_FALLBACK_ENABLED=true`, and only for a narrow set of retryable provider responses. Operational events contain route/outcome/byte counts, never source URLs or proxy credentials.

The bundled in-memory job store is for local and single-process verification. A durable store and external queue are required before multi-instance production. Cloud Tasks, Cloud Run Jobs, IAM, and deployment remain explicit operator steps.

The private, containerized backend for the Web Video Downloader trial.

The same private service also exposes an authenticated background-removal boundary for Streamnest tools. It accepts only private R2 object keys created for a matching job ID, runs the pinned `851-labs/background-remover` Replicate model, and copies the PNG result back to private R2 before returning a short-lived download URL. `REPLICATE_API_TOKEN` is optional for download-only deployments and required only for this tool endpoint.

## MVP boundaries

- Supports public, individual URLs from YouTube, TikTok, and Instagram.
- Rejects playlists, non-HTTPS URLs, private content, DRM-protected content, and user-supplied cookies.
- Enforces a maximum of 720p, 10 minutes, and 500 MB per trial job.
- Never exposes provider credentials or object-storage credentials to clients.

## Local development

```sh
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m uvicorn media_download_service.main:app --reload
```

Activate the virtual environment using your platform shell before running the commands. The application itself is platform-independent and is deployed in Docker.

Copy `.env.example` to `.env` and set only local credentials. The R2 bucket for this product is `download`; it must remain private. Never commit either environment file.

## Deployment model

The browser communicates only with the web application; it never calls this service directly. A production deployment should place the authenticated control service on Cloud Run and hand work to a durable queue/worker boundary. This repository does not create Cloud Tasks, Cloud Run Jobs, IAM bindings, or durable job storage; those remain production prerequisites.
