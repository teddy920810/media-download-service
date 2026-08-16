# Media Download Service

The private, containerized backend for the Web Video Downloader trial.

## MVP boundaries

- Supports public, individual URLs from YouTube, TikTok, and Instagram.
- Rejects playlists, non-HTTPS URLs, private content, DRM-protected content, and user-supplied cookies.
- Enforces a maximum of 720p, 10 minutes, and 500 MB per trial job.
- Never exposes provider credentials or object-storage credentials to clients.

## Local development

```sh
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m uvicorn media_download_service.main:app --reload
```

On Windows, activate the virtual environment using the platform shell before running the same Python commands. The application itself is platform-independent and is deployed in Docker.

Copy `.env.example` to `.env` and set only local credentials. The R2 bucket for this product is `download`; it must remain private. Never commit either environment file.

## Deployment model

Cloud Run hosts a small authenticated control service. It validates a signed job request and starts a Cloud Run Job that performs the download, uploads the result to private R2, then updates the application database. The browser communicates only with the web application; it never calls this service directly.
