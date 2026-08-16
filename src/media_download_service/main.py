import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from .inspection import default_inspector
from .policy import UrlPolicyError

app = FastAPI(title="Media Download Service", docs_url=None, redoc_url=None)


class InspectRequest(BaseModel):
    url: HttpUrl


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/inspect")
async def inspect(request: InspectRequest) -> dict[str, object]:
    try:
        return await asyncio.to_thread(default_inspector.inspect, str(request.url))
    except UrlPolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
