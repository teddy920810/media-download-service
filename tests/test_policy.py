import pytest

from media_download_service.policy import UrlPolicyError, inspect_url


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.youtube.com/watch?v=abc123", "youtube"),
        ("https://youtu.be/abc123", "youtube"),
        ("https://www.tiktok.com/@creator/video/123", "tiktok"),
        ("https://www.instagram.com/reel/abc123/", "instagram"),
    ],
)
def test_accepts_individual_urls_from_supported_platforms(url: str, platform: str) -> None:
    accepted = inspect_url(url)

    assert accepted.platform == platform
    assert accepted.url == url


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://www.youtube.com/watch?v=abc123", "Please enter a valid HTTPS URL."),
        ("https://example.com/video.mp4", "This platform is not supported yet."),
        ("https://www.youtube.com/watch?v=abc123&list=PL123", "Playlists are not available in the free trial."),
    ],
)
def test_rejects_urls_outside_the_trial_policy(url: str, message: str) -> None:
    with pytest.raises(UrlPolicyError, match=message):
        inspect_url(url)
