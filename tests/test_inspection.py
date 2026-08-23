from media_download_service.inspection import MediaInspector, YtDlpMetadataExtractor
from media_download_service.policy import MAX_FILE_BYTES
from yt_dlp.utils import DownloadError


class StubExtractor:
    def __init__(self, response):
        self.response = response

    def extract(self, url):
        return self.response


def test_youtube_inspection_uses_the_po_token_compatible_client(monkeypatch):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, _url, download):
            assert download is False
            return {"duration": 30, "formats": []}

    monkeypatch.setattr("media_download_service.inspection.YoutubeDL", FakeYoutubeDL)
    YtDlpMetadataExtractor("http://proxy.example").extract("https://www.youtube.com/watch?v=abc")

    assert captured["extractor_args"] == {"youtube": {"player_client": ["mweb"]}}
    assert captured["socket_timeout"] == 20
    assert captured["extractor_retries"] == 2


def test_youtube_inspection_retries_without_forced_client_when_formats_are_unavailable(monkeypatch):
    attempts = []

    class FakeYoutubeDL:
        def __init__(self, options):
            attempts.append(options)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, _url, download):
            assert download is False
            if len(attempts) == 1:
                raise DownloadError("Requested format is not available")
            return {"duration": 10_908, "formats": [{"format_id": "18"}]}

    monkeypatch.setattr("media_download_service.inspection.YoutubeDL", FakeYoutubeDL)

    result = YtDlpMetadataExtractor("http://proxy.example").extract(
        "https://www.youtube.com/watch?v=abc"
    )

    assert result["duration"] == 10_908
    assert attempts[0]["extractor_args"] == {"youtube": {"player_client": ["mweb"]}}
    assert "extractor_args" not in attempts[1]
    assert attempts[1]["proxy"] == "http://proxy.example"


def test_returns_all_downloadable_formats_without_trial_filtering():
    inspector = MediaInspector(
        StubExtractor(
            {
                "title": "A public video",
                "duration": 120,
                "formats": [
                    {"format_id": "720", "height": 720, "ext": "mp4", "vcodec": "avc1", "acodec": "mp4a", "filesize": 100},
                    {"format_id": "1080", "height": 1080, "ext": "mp4", "vcodec": "avc1", "acodec": "mp4a"},
                    {"format_id": "audio", "ext": "m4a", "vcodec": "none", "acodec": "mp4a", "abr": 128},
                    {"format_id": "large", "height": 720, "ext": "mp4", "vcodec": "avc1", "filesize": MAX_FILE_BYTES + 1},
                ],
            }
        )
    )

    result = inspector.inspect("https://www.youtube.com/watch?v=abc")

    assert result["title"] == "A public video"
    assert result["durationSeconds"] == 120
    assert result["formats"] == [
        {
            "formatId": "1080",
            "label": "1080p",
            "container": "mp4",
            "height": 1080,
            "hasVideo": True,
            "hasAudio": True,
            "audioBitrateKbps": None,
            "estimatedSizeBytes": None,
        },
        {
            "formatId": "720",
            "label": "720p",
            "container": "mp4",
            "height": 720,
            "hasVideo": True,
            "hasAudio": True,
            "audioBitrateKbps": None,
            "estimatedSizeBytes": 100,
        },
        {
            "formatId": "large",
            "label": "720p",
            "container": "mp4",
            "height": 720,
            "hasVideo": True,
            "hasAudio": False,
            "audioBitrateKbps": None,
            "estimatedSizeBytes": MAX_FILE_BYTES + 1,
        },
        {
            "formatId": "audio",
            "label": "128 kbps audio",
            "container": "m4a",
            "height": None,
            "hasVideo": False,
            "hasAudio": True,
            "audioBitrateKbps": 128,
            "estimatedSizeBytes": None,
        },
    ]


def test_reports_long_video_metadata_instead_of_rejecting_inspection():
    inspector = MediaInspector(
        StubExtractor(
            {
                "duration": 601,
                "formats": [
                    {"format_id": "18", "height": 360, "ext": "mp4", "vcodec": "avc", "acodec": "aac"}
                ],
            }
        )
    )

    assert inspector.inspect("https://www.youtube.com/watch?v=abc")["durationSeconds"] == 601


def test_allows_a_public_https_url_for_provider_inspection():
    inspector = MediaInspector(
        StubExtractor(
            {
                "duration": 30,
                "formats": [
                    {"format_id": "http", "height": 480, "ext": "mp4", "vcodec": "avc", "acodec": "aac"}
                ],
            }
        )
    )

    result = inspector.inspect("https://media.example.com/watch/123")

    assert result["platform"] == "other"
