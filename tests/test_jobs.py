from concurrent.futures import Future

import pytest

from media_download_service.jobs import DownloadJobConflict, DownloadJobCoordinator, InMemoryDownloadJobStore


class ManualExecutor:
    def __init__(self):
        self.tasks = []

    def submit(self, function, *args):
        self.tasks.append((function, args))
        return Future()

    def run_next(self):
        function, args = self.tasks.pop(0)
        function(*args)


def test_job_moves_from_queued_to_processing_to_ready():
    executor = ManualExecutor()
    store = InMemoryDownloadJobStore()
    coordinator = DownloadJobCoordinator(store, executor=executor)
    observed = []

    job = coordinator.enqueue(
        "job-1",
        "https://www.youtube.com/watch?v=abc",
        "18",
        lambda: observed.append(store.get("job-1").status) or {
            "objectKey": "trials/job-1/media.mp4",
            "downloadUrl": "https://signed.example/media",
            "sizeBytes": 42,
        },
    )

    assert job.status == "queued"
    executor.run_next()
    assert observed == ["processing"]
    assert store.get("job-1").status == "ready"


def test_same_job_request_is_idempotent_and_not_enqueued_twice():
    executor = ManualExecutor()
    coordinator = DownloadJobCoordinator(InMemoryDownloadJobStore(), executor=executor)
    first = coordinator.enqueue("job-1", "https://www.youtube.com/watch?v=abc", "18", lambda: {})
    second = coordinator.enqueue("job-1", "https://www.youtube.com/watch?v=abc", "18", lambda: {})

    assert second == first
    assert len(executor.tasks) == 1


def test_reusing_a_job_id_for_different_input_is_rejected():
    coordinator = DownloadJobCoordinator(InMemoryDownloadJobStore(), executor=ManualExecutor())
    coordinator.enqueue("job-1", "https://www.youtube.com/watch?v=abc", "18", lambda: {})

    with pytest.raises(DownloadJobConflict):
        coordinator.enqueue("job-1", "https://www.youtube.com/watch?v=different", "18", lambda: {})


def test_transient_failure_retries_once_then_succeeds():
    executor = ManualExecutor()
    store = InMemoryDownloadJobStore()
    coordinator = DownloadJobCoordinator(store, executor=executor, max_attempts=2)
    attempts = []

    def process():
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("temporary storage failure")
        return {"objectKey": "trials/job-1/media.mp4", "downloadUrl": "https://signed", "sizeBytes": 5}

    coordinator.enqueue("job-1", "https://www.youtube.com/watch?v=abc", "18", process)
    executor.run_next()

    assert len(attempts) == 2
    assert store.get("job-1").status == "ready"
    assert store.get("job-1").attempts == 2


def test_exhausted_retry_has_a_safe_public_error():
    executor = ManualExecutor()
    store = InMemoryDownloadJobStore()
    coordinator = DownloadJobCoordinator(store, executor=executor, max_attempts=2)
    coordinator.enqueue("job-1", "https://www.youtube.com/watch?v=abc", "18", lambda: 1 / 0)
    executor.run_next()

    job = store.get("job-1")
    assert job.status == "failed"
    assert job.error == "Unable to prepare this download right now."


def test_invalid_processor_result_fails_safely():
    executor = ManualExecutor()
    store = InMemoryDownloadJobStore()
    coordinator = DownloadJobCoordinator(store, executor=executor, max_attempts=1)
    coordinator.enqueue(
        "job-1",
        "https://www.youtube.com/watch?v=abc",
        "18",
        lambda: {
            "objectKey": "trials/job-1/media.mp4",
            "downloadUrl": "https://signed",
            "sizeBytes": "5",
        },
    )
    executor.run_next()

    job = store.get("job-1")
    assert job.status == "failed"
    assert job.error == "Unable to prepare this download right now."
