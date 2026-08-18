import asyncio
import secrets
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, HttpUrl
from yt_dlp.utils import DownloadError

from .config import Settings, get_settings
from .download import default_download_worker
from .inspection import default_inspector
from .policy import UrlPolicyError
from .storage import R2Storage

app = FastAPI(title="Media Download Service", docs_url=None, redoc_url=None)


class InspectRequest(BaseModel):
    url: HttpUrl


class DownloadRequest(BaseModel):
    jobId: UUID
    url: HttpUrl
    formatId: str


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/inspect")
async def inspect(
    request: InspectRequest,
    x_internal_service_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_internal_token(x_internal_service_token)
    try:
        return await asyncio.to_thread(default_inspector.inspect, str(request.url))
    except UrlPolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except DownloadError as error:
        raise HTTPException(
            status_code=422,
            detail="This provider is temporarily requiring additional verification. Please try another link later.",
        ) from error


@app.post("/v1/downloads")
async def create_download(
    request: DownloadRequest,
    x_internal_service_token: str | None = Header(default=None),
) -> dict[str, object]:
    settings = require_internal_token(x_internal_service_token)

    try:
        return await asyncio.to_thread(_download_and_store, request, settings)
    except UrlPolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to prepare this download right now.") from None


def require_internal_token(token: str | None) -> Settings:
    settings = get_settings()
    if not token or not secrets.compare_digest(token, settings.internal_service_token):
        raise HTTPException(status_code=401, detail="Unauthorized service request.")
    return settings


def _download_and_store(request: DownloadRequest, settings: Settings) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="media-trial-") as temporary_directory:
        result = default_download_worker.download(request.url.unicode_string(), request.formatId, Path(temporary_directory))
        path = result["path"]
        assert isinstance(path, Path)
        object_key = f"trials/{request.jobId}/media{path.suffix.lower()}"
        storage = R2Storage(settings)
        storage.upload(path, object_key, str(result["contentType"]))
        return {
            "jobId": str(request.jobId),
            "objectKey": object_key,
            "downloadUrl": storage.temporary_download_url(object_key),
            "sizeBytes": result["sizeBytes"],
        }
