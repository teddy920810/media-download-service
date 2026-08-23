import pytest

from yt_dlp.utils import DownloadError

from media_download_service.download import (
    ProxyFallbackDownloader,
    TrialDownloadWorker,
    YtDlpFileDownloader,
)
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


def test_youtube_download_uses_the_po_token_compatible_client(monkeypatch, tmp_path):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def download(self, _urls):
            (tmp_path / "media.mp4").write_bytes(b"video")
            return 0

    monkeypatch.setattr("media_download_service.download.YoutubeDL", FakeYoutubeDL)
    YtDlpFileDownloader("http://proxy.example").download(
        "https://www.youtube.com/watch?v=abc", "18", tmp_path
    )

    assert captured["extractor_args"] == {"youtube": {"player_client": ["mweb"]}}
    assert captured["socket_timeout"] == 30
    assert captured["retries"] == 2


def test_downloads_only_an_audio_inclusive_format(tmp_path):
    downloader = StubDownloader()
    worker = TrialDownloadWorker(MediaInspector(StubExtractor()), downloader)

    result = worker.download("https://www.youtube.com/watch?v=abc", "with-audio", tmp_path)

    assert downloader.calls == [("https://www.youtube.com/watch?v=abc", "with-audio")]
    assert result["contentType"] == "video/mp4"
    assert result["sizeBytes"] == 5


def test_combines_video_only_format_with_the_best_available_audio(tmp_path):
    downloader = StubDownloader()
    worker = TrialDownloadWorker(MediaInspector(StubExtractor()), downloader)

    worker.download("https://www.youtube.com/watch?v=abc", "video-only", tmp_path)

    assert downloader.calls == [
        ("https://www.youtube.com/watch?v=abc", "video-only+bestaudio/best")
    ]


def test_rejects_web_download_when_video_exceeds_720p(tmp_path):
    class HighResolutionExtractor:
        def extract(self, url):
            return {
                "duration": 30,
                "formats": [
                    {"format_id": "1080", "height": 1080, "ext": "mp4", "vcodec": "avc", "acodec": "aac"}
                ],
            }

    worker = TrialDownloadWorker(MediaInspector(HighResolutionExtractor()), StubDownloader())

    with pytest.raises(UrlPolicyError, match="720p"):
        worker.download("https://www.youtube.com/watch?v=abc", "1080", tmp_path)


def test_rejects_web_download_when_video_is_longer_than_ten_minutes(tmp_path):
    class LongVideoExtractor:
        def extract(self, url):
            return {
                "duration": 601,
                "formats": [
                    {"format_id": "18", "height": 360, "ext": "mp4", "vcodec": "avc", "acodec": "aac"}
                ],
            }

    worker = TrialDownloadWorker(MediaInspector(LongVideoExtractor()), StubDownloader())

    with pytest.raises(UrlPolicyError, match="10 minutes"):
        worker.download("https://www.youtube.com/watch?v=abc", "18", tmp_path)


class RecordingDownloader:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = 0

    def download(self, url, format_id, destination):
        self.calls += 1
        if self.failure:
            raise self.failure
        output = destination / "media.mp4"
        output.write_bytes(b"video")
        return output


def test_download_stays_direct_when_the_direct_attempt_succeeds(tmp_path):
    direct = RecordingDownloader()
    proxy = RecordingDownloader()
    events = []
    downloader = ProxyFallbackDownloader(direct, proxy, True, events.append)

    result = downloader.download("https://www.youtube.com/watch?v=abc", "18", tmp_path)

    assert result.name == "media.mp4"
    assert direct.calls == 1
    assert proxy.calls == 0
    assert events == [{"operation": "download", "route": "direct", "outcome": "success", "sizeBytes": 5}]


def test_download_uses_proxy_only_for_an_explicit_retryable_fallback(tmp_path):
    direct = RecordingDownloader(DownloadError("HTTP Error 429: Too Many Requests"))
    proxy = RecordingDownloader()
    events = []
    downloader = ProxyFallbackDownloader(direct, proxy, True, events.append)

    downloader.download("https://www.youtube.com/watch?v=abc", "18", tmp_path)

    assert proxy.calls == 1
    assert [event["route"] for event in events] == ["direct", "proxy"]
    assert all("url" not in event and "proxy" not in event for event in events)


@pytest.mark.parametrize("allow_fallback", [False, True])
def test_download_does_not_proxy_non_retryable_provider_errors(tmp_path, allow_fallback):
    direct = RecordingDownloader(DownloadError("Requested format is not available"))
    proxy = RecordingDownloader()
    downloader = ProxyFallbackDownloader(direct, proxy, allow_fallback)

    with pytest.raises(DownloadError, match="Requested format"):
        downloader.download("https://www.youtube.com/watch?v=abc", "18", tmp_path)

    assert proxy.calls == 0
