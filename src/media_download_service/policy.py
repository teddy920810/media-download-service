from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

MAX_DURATION_SECONDS = 10 * 60
MAX_FILE_BYTES = 500 * 1024 * 1024
MAX_HEIGHT = 720

PLATFORM_HOSTS = {
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"},
    "tiktok": {"tiktok.com", "www.tiktok.com", "vm.tiktok.com"},
    "instagram": {"instagram.com", "www.instagram.com", "instagr.am"},
}


@dataclass(frozen=True)
class AcceptedUrl:
    platform: str
    url: str


class UrlPolicyError(ValueError):
    pass


def inspect_url(raw_url: str) -> AcceptedUrl:
    parsed = urlparse(raw_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UrlPolicyError("Please enter a valid HTTPS URL.")

    hostname = parsed.hostname.lower()
    platform = next((name for name, hosts in PLATFORM_HOSTS.items() if hostname in hosts), None)
    if platform is None:
        raise UrlPolicyError("This platform is not supported yet.")

    if platform == "youtube" and (parsed.path == "/playlist" or "list" in parse_qs(parsed.query)):
        raise UrlPolicyError("Playlists are not available in the free trial.")

    return AcceptedUrl(platform=platform, url=raw_url)
