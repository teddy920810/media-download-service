from pathlib import Path

from media_download_service.config import Settings
from media_download_service.storage import R2Storage


class StubS3:
    def __init__(self):
        self.uploads = []
        self.presigns = []

    def upload_file(self, filename, bucket, key, ExtraArgs):
        self.uploads.append((filename, bucket, key, ExtraArgs))

    def put_object(self, **kwargs):
        self.uploads.append(kwargs)

    def head_object(self, **kwargs):
        return {"ContentLength": 42}

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        assert operation == "get_object"
        self.presigns.append((Params, ExpiresIn))
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


def test_background_tool_uses_private_signed_input_and_byte_uploads():
    client = StubS3()
    storage = R2Storage(settings(), client)

    assert storage.exists("tool-inputs/background-remover/input.png") is True
    assert storage.temporary_input_url("tool-inputs/background-remover/input.png") == "https://download.example.test/signed"
    storage.upload_bytes(b"transparent-png", "tool-results/background-remover/job.png", "image/png")

    assert client.uploads == [
        {
            "Bucket": "download",
            "Key": "tool-results/background-remover/job.png",
            "Body": b"transparent-png",
            "ContentType": "image/png",
        }
    ]
    assert client.presigns == [
        ({"Bucket": "download", "Key": "tool-inputs/background-remover/input.png"}, 600)
    ]


def test_creates_short_lived_download_url():
    client = StubS3()
    assert (
        R2Storage(settings(), client).temporary_download_url(
            "trials/job-1/video.mp4",
            download_name="streamnest-video.mp4",
        )
        == "https://download.example.test/signed"
    )
    assert client.presigns == [
        (
            {
                "Bucket": "download",
                "Key": "trials/job-1/video.mp4",
                "ResponseContentDisposition": (
                    'attachment; filename="streamnest-video.mp4"; '
                    "filename*=UTF-8''streamnest-video.mp4"
                ),
            },
            900,
        )
    ]


def test_download_filename_is_sanitized_before_signing():
    client = StubS3()

    R2Storage(settings(), client).temporary_download_url(
        "tool-results/background-remover/job.png",
        download_name='unsafe\r\nname".png',
    )

    params, _ = client.presigns[0]
    assert params["ResponseContentDisposition"] == (
        'attachment; filename="unsafe__name_.png"; filename*=UTF-8\'\'unsafe__name_.png'
    )
