from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .inspection import MediaInspector, default_inspector
from .observability import observe_transfer
from .policy import MAX_FILE_BYTES, UrlPolicyError
from .proxy import load_proxy_configuration


class FileDownloader(Protocol):
    def download(self, url: str, format_id: str, destination: Path) -> Path: ...


class YtDlpFileDownloader:
    def __init__(self, proxy_url: str | None = None):
        self.proxy_url = proxy_url

    def download(self, url: str, format_id: str, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        options = {
            "extractor_args": {"youtube": {"player_client": ["mweb"]}},
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": format_id,
            "max_filesize": MAX_FILE_BYTES,
            "socket_timeout": 30,
            "retries": 2,
            "fragment_retries": 2,
            "outtmpl": str(destination / "media.%(ext)s"),
        }
        if self.proxy_url:
            options["proxy"] = self.proxy_url
        with YoutubeDL(options) as downloader:
            code = downloader.download([url])
        if code != 0:
            raise UrlPolicyError("The provider could not prepare this format.")

        files = [path for path in destination.iterdir() if path.is_file()]
        if len(files) != 1:
            raise UrlPolicyError("The provider returned an unexpected download result.")
        output = files[0]
        if output.stat().st_size > MAX_FILE_BYTES:
            output.unlink(missing_ok=True)
            raise UrlPolicyError("This file exceeds the 500 MB free-trial limit.")
        return output


ObservationSink = Callable[[dict[str, object]], None]


def _is_retryable_provider_error(error: DownloadError) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "http error 403",
            "http error 429",
            "too many requests",
            "temporarily unavailable",
            "not available in your country",
            "geo-restricted",
        )
    )


class ProxyFallbackDownloader:
    """Prefer direct media transfer and spend proxy traffic only on narrow failures."""

    def __init__(
        self,
        direct: FileDownloader,
        proxy: FileDownloader | None,
        allow_fallback: bool,
        observe: ObservationSink | None = None,
    ):
        self.direct = direct
        self.proxy = proxy
        self.allow_fallback = allow_fallback
        self.observe = observe or (lambda _event: None)

    def download(self, url: str, format_id: str, destination: Path) -> Path:
        try:
            output = self.direct.download(url, format_id, destination)
            self._success("direct", output)
            return output
        except DownloadError as error:
            retryable = _is_retryable_provider_error(error)
            self.observe({"operation": "download", "route": "direct", "outcome": "provider_error", "retryable": retryable})
            if not retryable or not self.allow_fallback or self.proxy is None:
                raise

        for path in destination.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)
        try:
            output = self.proxy.download(url, format_id, destination)
            self._success("proxy", output)
            return output
        except DownloadError:
            self.observe({"operation": "download", "route": "proxy", "outcome": "provider_error", "retryable": False})
            raise

    def _success(self, route: str, output: Path) -> None:
        self.observe(
            {
                "operation": "download",
                "route": route,
                "outcome": "success",
                "sizeBytes": output.stat().st_size,
            }
        )


@dataclass(frozen=True)
class TrialDownloadWorker:
    inspector: MediaInspector
    downloader: FileDownloader

    def download(self, url: str, format_id: str, destination: Path) -> dict[str, Any]:
        media = self.inspector.inspect(url)
        allowed = next(
            (
                item
                for item in media["formats"]
                if item["formatId"] == format_id and item["hasAudio"]
            ),
            None,
        )
        if allowed is None:
            raise UrlPolicyError("Choose an available format that includes audio.")
        try:
            output = self.downloader.download(media["sourceUrl"], format_id, destination)
        except DownloadError as error:
            raise UrlPolicyError("This provider did not make the selected format available for download.") from error
        return {
            "path": output,
            "contentType": self._content_type(allowed["container"]),
            "sizeBytes": output.stat().st_size,
            "title": media["title"],
        }

    @staticmethod
    def _content_type(container: str) -> str:
        return {"mp4": "video/mp4", "webm": "video/webm", "mkv": "video/x-matroska"}.get(container, "application/octet-stream")


proxy_configuration = load_proxy_configuration()
default_download_worker = TrialDownloadWorker(
    inspector=default_inspector,
    downloader=ProxyFallbackDownloader(
        direct=YtDlpFileDownloader(),
        proxy=(
            YtDlpFileDownloader(proxy_url=proxy_configuration.download_proxy_url)
            if proxy_configuration.download_proxy_url
            else None
        ),
        allow_fallback=proxy_configuration.allow_download_proxy_fallback,
        observe=observe_transfer,
    ),
)
