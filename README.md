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
python -m pip install -c requirements.lock -e ".[dev]"
python -m pip check
python -m pytest
python -m uvicorn media_download_service.main:app --reload
```

Activate the virtual environment using your platform shell before running the commands. The application itself is platform-independent and is deployed in Docker.

Docker installs runtime dependencies from `requirements.lock`, then installs the application without resolving dependencies again. CI and local development constrain runtime dependencies to the same versions. Keep the lock's transitive dependencies and platform markers complete when updating it; the dependency-security tests check the installed dependency graph, including extras.

The runtime lock preserves the application dependencies observed in the serving Cloud Run image on 2026-10-22, including yt-dlp 2026.8.19, while upgrading certifi and urllib3 for the security fixes below. The yt-dlp minimum also retains that verified production baseline for installations outside the lock.

`certifi>=2026.10.19` is the compatibility-preserving security floor for [GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2): 2026.10.18 removed all emSign roots, and 2026.10.19 restored the unaffected roots while leaving the compromised ECC G3 root excluded. `urllib3>=2.8.0` also addresses the existing lock's [chunk-size buffering](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw), [Deflate streaming](https://github.com/urllib3/urllib3/security/advisories/GHSA-gh4c-6fx4-qh6g), and [HTTPS proxy TLS](https://github.com/urllib3/urllib3/security/advisories/GHSA-8988-9cw3-xx77) advisories. Keep TLS and hostname verification enabled.

A passing source test or rebuilt image does not establish the versions in an already-running Cloud Run revision; inspect that revision's immutable image separately before declaring production remediated.

Copy `.env.example` to `.env` and set only local credentials. The R2 bucket for this product is `download`; it must remain private. Never commit either environment file.

## Deployment model

The browser communicates only with the web application; it never calls this service directly. A production deployment should place the authenticated control service on Cloud Run and hand work to a durable queue/worker boundary. This repository does not create Cloud Tasks, Cloud Run Jobs, IAM bindings, or durable job storage; those remain production prerequisites.
