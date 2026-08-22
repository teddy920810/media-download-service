from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import Lock
from typing import Literal, Protocol, TypedDict

from .observability import observe_transfer
from .policy import UrlPolicyError


JobStatus = Literal["queued", "processing", "ready", "failed"]


class JobResult(TypedDict):
    objectKey: str
    downloadUrl: str
    sizeBytes: int


JobProcessor = Callable[[], Mapping[str, object]]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_job_result(result: Mapping[str, object]) -> JobResult:
    object_key = result.get("objectKey")
    download_url = result.get("downloadUrl")
    size_bytes = result.get("sizeBytes")
    if not isinstance(object_key, str) or not object_key:
        raise ValueError("Worker result has an invalid object key.")
    if not isinstance(download_url, str) or not download_url:
        raise ValueError("Worker result has an invalid download URL.")
    if type(size_bytes) is not int or size_bytes < 0:
        raise ValueError("Worker result has an invalid size.")
    return {"objectKey": object_key, "downloadUrl": download_url, "sizeBytes": size_bytes}


@dataclass(frozen=True)
class DownloadJob:
    job_id: str
    source_url: str
    format_id: str
    status: JobStatus
    attempts: int
    object_key: str | None = None
    download_url: str | None = None
    size_bytes: int | None = None
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def public(self) -> dict[str, object]:
        result: dict[str, object] = {"jobId": self.job_id, "status": self.status}
        if self.status == "ready":
            result.update(
                {
                    "objectKey": self.object_key,
                    "downloadUrl": self.download_url,
                    "sizeBytes": self.size_bytes,
                }
            )
        elif self.status == "failed":
            result["error"] = self.error
        return result


class DownloadJobConflict(Exception):
    pass


class DownloadJobStore(Protocol):
    def create_or_get(self, job: DownloadJob) -> tuple[DownloadJob, bool]: ...
    def get(self, job_id: str) -> DownloadJob | None: ...
    def save(self, job: DownloadJob) -> None: ...


class InMemoryDownloadJobStore:
    """Cross-platform local store; replace with a durable adapter before multi-instance production."""

    def __init__(self) -> None:
        self._jobs: dict[str, DownloadJob] = {}
        self._lock = Lock()

    def create_or_get(self, job: DownloadJob) -> tuple[DownloadJob, bool]:
        with self._lock:
            existing = self._jobs.get(job.job_id)
            if existing is not None:
                return existing, False
            self._jobs[job.job_id] = job
            return job, True

    def get(self, job_id: str) -> DownloadJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def save(self, job: DownloadJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job


class DownloadJobCoordinator:
    def __init__(
        self,
        store: DownloadJobStore,
        executor: Executor | None = None,
        max_attempts: int = 2,
    ) -> None:
        self.store = store
        self.executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="media-download")
        self.max_attempts = max_attempts

    def enqueue(self, job_id: str, source_url: str, format_id: str, processor: JobProcessor) -> DownloadJob:
        timestamp = _now()
        queued = DownloadJob(job_id, source_url, format_id, "queued", 0, created_at=timestamp, updated_at=timestamp)
        job, created = self.store.create_or_get(queued)
        if not created:
            if job.source_url != source_url or job.format_id != format_id:
                raise DownloadJobConflict("A job ID cannot be reused for different input.")
            return job
        self.executor.submit(self._run, job_id, processor)
        return queued

    def get(self, job_id: str) -> DownloadJob | None:
        return self.store.get(job_id)

    def _run(self, job_id: str, processor: JobProcessor) -> None:
        for attempt in range(1, self.max_attempts + 1):
            current = self.store.get(job_id)
            if current is None or current.status in {"ready", "failed"}:
                return
            processing = replace(current, status="processing", attempts=attempt, updated_at=_now())
            self.store.save(processing)
            observe_transfer({"operation": "job", "route": "worker", "outcome": "attempt", "attempt": attempt})
            try:
                result = _validate_job_result(processor())
                ready = replace(
                    processing,
                    status="ready",
                    object_key=str(result["objectKey"]),
                    download_url=str(result["downloadUrl"]),
                    size_bytes=result["sizeBytes"],
                    error=None,
                    updated_at=_now(),
                )
                self.store.save(ready)
                observe_transfer({"operation": "job", "route": "worker", "outcome": "success", "attempt": attempt, "sizeBytes": ready.size_bytes or 0})
                return
            except UrlPolicyError as error:
                self.store.save(replace(processing, status="failed", error=str(error), updated_at=_now()))
                observe_transfer({"operation": "job", "route": "worker", "outcome": "policy_error", "attempt": attempt})
                return
            except Exception:
                if attempt == self.max_attempts:
                    self.store.save(
                        replace(
                            processing,
                            status="failed",
                            error="Unable to prepare this download right now.",
                            updated_at=_now(),
                        )
                    )
                    observe_transfer({"operation": "job", "route": "worker", "outcome": "failed", "attempt": attempt})


default_download_jobs = DownloadJobCoordinator(InMemoryDownloadJobStore())
