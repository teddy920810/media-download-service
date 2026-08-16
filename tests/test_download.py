from pathlib import Path

import pytest

from media_download_service.download import TrialDownloadWorker
from media_download_service.inspection import MediaInspector
from media_download_service.policy import UrlPolicyError


class StubExtractor:
    def extract(self, url):
        return {
            "title": "Trial video",
            "duration": 30,
            "formats": [
                {"format_id": "with-audio", "height": 360, "ext": "mp4", "vcodec": "avc", "acodec": "aac"},
                {"format_id": "video-only", "height": 720, "ext": "mp4", "vcodec": "avc", "acodec": "none"},
            ],
        }


class StubDownloader:
    def __init__(self):
        self.calls = []

    def download(self, url, format_id, destination):
        self.calls.append((url, format_id))
        output = destination / "media.mp4"
        output.write_bytes(b"video")
        return output


def test_downloads_only_an_audio_inclusive_format(tmp_path):
    downloader = StubDownloader()
    worker = TrialDownloadWorker(MediaInspector(StubExtractor()), downloader)

    result = worker.download("https://www.youtube.com/watch?v=abc", "with-audio", tmp_path)

    assert downloader.calls == [("https://www.youtube.com/watch?v=abc", "with-audio")]
    assert result["contentType"] == "video/mp4"
    assert result["sizeBytes"] == 5


def test_rejects_video_only_format(tmp_path):
    worker = TrialDownloadWorker(MediaInspector(StubExtractor()), StubDownloader())

    with pytest.raises(UrlPolicyError, match="includes audio"):
        worker.download("https://www.youtube.com/watch?v=abc", "video-only", tmp_path)
