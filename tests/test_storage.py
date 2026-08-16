from pathlib import Path

from media_download_service.config import Settings
from media_download_service.storage import R2Storage


class StubS3:
    def __init__(self):
        self.uploads = []

    def upload_file(self, filename, bucket, key, ExtraArgs):
        self.uploads.append((filename, bucket, key, ExtraArgs))

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        assert operation == "get_object"
        assert Params == {"Bucket": "download", "Key": "trials/job-1/video.mp4"}
        assert ExpiresIn == 900
        return "https://download.example.test/signed"


def settings() -> Settings:
    return Settings("token", "account", "key", "secret", "download", "https://r2.example.test")


def test_uploads_to_private_download_bucket(tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    client = StubS3()
    storage = R2Storage(settings(), client)

    storage.upload(source, "trials/job-1/video.mp4", "video/mp4")

    assert client.uploads == [(str(source), "download", "trials/job-1/video.mp4", {"ContentType": "video/mp4"})]


def test_creates_short_lived_download_url():
    assert R2Storage(settings(), StubS3()).temporary_download_url("trials/job-1/video.mp4") == "https://download.example.test/signed"
