from fastapi.testclient import TestClient
from yt_dlp.utils import DownloadError

from media_download_service import main
from media_download_service.jobs import DownloadJobCoordinator, InMemoryDownloadJobStore


class Settings:
    internal_service_token = "test-token"


def test_download_endpoint_requires_internal_token(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings())
    response = TestClient(main.app).post(
        "/v1/downloads",
        json={"jobId": "2d05763e-faa5-495f-979f-8852b16ea0c1", "url": "https://www.youtube.com/watch?v=abc", "formatId": "18"},
    )
    assert response.status_code == 401


def test_inspect_endpoint_requires_internal_token(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings())
    response = TestClient(main.app).post(
        "/v1/inspect",
        json={"url": "https://www.youtube.com/watch?v=abc"},
    )
    assert response.status_code == 401


def test_inspect_endpoint_hides_provider_verification_details(monkeypatch):
    class RejectingInspector:
        def inspect(self, url):
            raise DownloadError("provider authentication details")

    monkeypatch.setattr(main, "get_settings", lambda: Settings())
    monkeypatch.setattr(main, "default_inspector", RejectingInspector())
    response = TestClient(main.app).post(
        "/v1/inspect",
        headers={"X-Internal-Service-Token": "test-token"},
        json={"url": "https://www.youtube.com/watch?v=abc"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": "This provider is temporarily requiring additional verification. Please try another link later."
    }


def test_download_endpoint_queues_work_and_returns_202(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings())
    store = InMemoryDownloadJobStore()
    monkeypatch.setattr(main, "download_jobs", DownloadJobCoordinator(store))
    monkeypatch.setattr(
        main,
        "_download_and_store",
        lambda request, settings: {"jobId": str(request.jobId), "objectKey": "trials/job/media.mp4", "downloadUrl": "https://signed.example.test", "sizeBytes": 42},
    )
    response = TestClient(main.app).post(
        "/v1/downloads",
        headers={"X-Internal-Service-Token": "test-token"},
        json={"jobId": "2d05763e-faa5-495f-979f-8852b16ea0c1", "url": "https://www.youtube.com/watch?v=abc", "formatId": "18"},
    )
    assert response.status_code == 202
    assert response.json() == {
        "jobId": "2d05763e-faa5-495f-979f-8852b16ea0c1",
        "status": "queued",
    }


def test_download_status_returns_the_current_job(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings())
    store = InMemoryDownloadJobStore()
    coordinator = DownloadJobCoordinator(store)
    monkeypatch.setattr(main, "download_jobs", coordinator)
    coordinator.enqueue(
        "2d05763e-faa5-495f-979f-8852b16ea0c1",
        "https://www.youtube.com/watch?v=abc",
        "18",
        lambda: {"objectKey": "trials/job/media.mp4", "downloadUrl": "https://signed.example.test", "sizeBytes": 42},
    )
    for _ in range(100):
        if store.get("2d05763e-faa5-495f-979f-8852b16ea0c1").status == "ready":
            break

    response = TestClient(main.app).get(
        "/v1/downloads/2d05763e-faa5-495f-979f-8852b16ea0c1",
        headers={"X-Internal-Service-Token": "test-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] in {"processing", "ready"}
