from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from .policy import MAX_DURATION_SECONDS, MAX_FILE_BYTES, MAX_HEIGHT, UrlPolicyError, inspect_url

app = FastAPI(title="Media Download Service", docs_url=None, redoc_url=None)


class InspectRequest(BaseModel):
    url: HttpUrl


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/inspect")
def inspect(request: InspectRequest) -> dict[str, int | str]:
    try:
        accepted = inspect_url(str(request.url))
    except UrlPolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "platform": accepted.platform,
        "url": accepted.url,
        "maxHeight": MAX_HEIGHT,
        "maxDurationSeconds": MAX_DURATION_SECONDS,
        "maxFileBytes": MAX_FILE_BYTES,
    }
