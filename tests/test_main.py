from fastapi.testclient import TestClient

from media_download_service import main


class Settings:
    internal_service_token = "test-token"


def test_download_endpoint_requires_internal_token(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings())
    response = TestClient(main.app).post(
        "/v1/downloads",
        json={"jobId": "2d05763e-faa5-495f-979f-8852b16ea0c1", "url": "https://www.youtube.com/watch?v=abc", "formatId": "18"},
    )
    assert response.status_code == 401


def test_download_endpoint_returns_temporary_url(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings())
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
    assert response.status_code == 200
    assert response.json()["downloadUrl"] == "https://signed.example.test"
