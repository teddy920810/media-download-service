import pytest

from media_download_service.inspection import MediaInspector, YtDlpMetadataExtractor
from media_download_service.policy import MAX_FILE_BYTES, UrlPolicyError


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


def test_returns_only_trial_eligible_formats():
    inspector = MediaInspector(
        StubExtractor(
            {
                "title": "A public video",
                "duration": 120,
                "formats": [
                    {"format_id": "720", "height": 720, "ext": "mp4", "vcodec": "avc1", "acodec": "mp4a", "filesize": 100},
                    {"format_id": "1080", "height": 1080, "ext": "mp4", "vcodec": "avc1", "acodec": "mp4a"},
                    {"format_id": "audio", "ext": "m4a", "vcodec": "none", "acodec": "mp4a"},
                    {"format_id": "large", "height": 720, "ext": "mp4", "vcodec": "avc1", "filesize": MAX_FILE_BYTES + 1},
                ],
            }
        )
    )

    result = inspector.inspect("https://www.youtube.com/watch?v=abc")

    assert result["title"] == "A public video"
    assert result["durationSeconds"] == 120
    assert result["formats"] == [{"formatId": "720", "label": "720p", "container": "mp4", "height": 720, "hasAudio": True, "estimatedSizeBytes": 100}]


def test_rejects_video_longer_than_trial_limit():
    inspector = MediaInspector(StubExtractor({"duration": 601, "formats": []}))

    with pytest.raises(UrlPolicyError, match="10 minutes"):
        inspector.inspect("https://www.youtube.com/watch?v=abc")
