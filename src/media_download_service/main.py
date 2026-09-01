import asyncio
import secrets
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field, HttpUrl, model_validator
from yt_dlp.utils import DownloadError

from .background import ReplicateBackgroundRemover
from .config import Settings, get_settings
from .download import default_download_worker
from .inspection import default_inspector
from .jobs import DownloadJobConflict, default_download_jobs
from .observability import observe_transfer
from .policy import UrlPolicyError
from .storage import R2Storage

app = FastAPI(title="Media Download Service", docs_url=None, redoc_url=None)
download_jobs = default_download_jobs


class InspectRequest(BaseModel):
    url: HttpUrl


class DownloadRequest(BaseModel):
    jobId: UUID
    url: HttpUrl
    formatId: str


class BackgroundRemovalRequest(BaseModel):
    jobId: UUID
    inputKey: str = Field(
        pattern=r"^tool-inputs/background-remover/[0-9a-f-]{36}\.(?:jpg|png|webp)$",
        max_length=160,
    )

    @model_validator(mode="after")
    def require_job_owned_input(self) -> "BackgroundRemovalRequest":
        object_id = self.inputKey.rsplit("/", 1)[-1].split(".", 1)[0]
        if object_id != str(self.jobId):
            raise ValueError("The uploaded image must belong to this job.")
        return self


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
        result = await asyncio.to_thread(default_inspector.inspect, str(request.url))
        observe_transfer({"operation": "inspect", "route": "service", "outcome": "success"})
        return result
    except UrlPolicyError as error:
        observe_transfer({"operation": "inspect", "route": "service", "outcome": "policy_error"})
        raise HTTPException(status_code=400, detail=str(error)) from error
    except DownloadError as error:
        observe_transfer({"operation": "inspect", "route": "service", "outcome": "provider_error"})
        raise HTTPException(
            status_code=422,
            detail="This provider is temporarily requiring additional verification. Please try another link later.",
        ) from error


@app.post("/v1/downloads")
async def create_download(
    request: DownloadRequest,
    response: Response,
    x_internal_service_token: str | None = Header(default=None),
) -> dict[str, object]:
    settings = require_internal_token(x_internal_service_token)
    try:
        job = download_jobs.enqueue(
            str(request.jobId),
            request.url.unicode_string(),
            request.formatId,
            lambda: _download_and_store(request, settings),
        )
    except DownloadJobConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    response.status_code = 202 if job.status == "queued" else 200
    return {"jobId": str(request.jobId), "status": job.status}


@app.get("/v1/downloads/{job_id}")
async def get_download(
    job_id: UUID,
    x_internal_service_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_internal_token(x_internal_service_token)
    job = download_jobs.get(str(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Download job not found.")
    return job.public()


@app.post("/v1/background-removals")
async def create_background_removal(
    request: BackgroundRemovalRequest,
    x_internal_service_token: str | None = Header(default=None),
) -> dict[str, object]:
    settings = require_internal_token(x_internal_service_token)
    if not settings.replicate_api_token:
        raise HTTPException(status_code=503, detail="The background removal service is not configured yet.")
    try:
        result = await asyncio.to_thread(_remove_background_and_store, request, settings)
        observe_transfer(
            {
                "operation": "background_remove",
                "route": "service",
                "outcome": "success",
                "sizeBytes": result["sizeBytes"],
            }
        )
        return result
    except FileNotFoundError as error:
        observe_transfer({"operation": "background_remove", "route": "service", "outcome": "missing_input"})
        raise HTTPException(status_code=404, detail="The uploaded image was not found.") from error
    except Exception as error:
        observe_transfer({"operation": "background_remove", "route": "service", "outcome": "provider_error"})
        raise HTTPException(
            status_code=502,
            detail="Unable to remove the image background right now.",
        ) from error


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
            "downloadUrl": storage.temporary_download_url(
                object_key,
                download_name=f"streamnest-video{path.suffix.lower()}",
            ),
            "sizeBytes": result["sizeBytes"],
        }


def _remove_background_and_store(
    request: BackgroundRemovalRequest,
    settings: Settings,
) -> dict[str, object]:
    storage = R2Storage(settings)
    if not storage.exists(request.inputKey):
        raise FileNotFoundError(request.inputKey)
    result_key = f"tool-results/background-remover/{request.jobId}.png"
    if storage.exists(result_key):
        size = storage.size(result_key)
    else:
        remover = ReplicateBackgroundRemover(settings.replicate_api_token or "")
        content = remover.remove(storage.temporary_input_url(request.inputKey))
        storage.upload_bytes(content, result_key, "image/png")
        size = len(content)
    return {
        "jobId": str(request.jobId),
        "status": "ready",
        "objectKey": result_key,
        "downloadUrl": storage.temporary_download_url(
            result_key,
            download_name="streamnest-background-removed.png",
        ),
        "sizeBytes": size,
    }
