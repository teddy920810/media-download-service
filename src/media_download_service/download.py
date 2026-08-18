from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .inspection import MediaInspector, default_inspector
from .policy import MAX_FILE_BYTES, UrlPolicyError
from .proxy import build_decodo_proxy_url


class FileDownloader(Protocol):
    def download(self, url: str, format_id: str, destination: Path) -> Path: ...


class YtDlpFileDownloader:
    def __init__(self, proxy_url: str | None = None):
        self.proxy_url = proxy_url

    def download(self, url: str, format_id: str, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": format_id,
            "max_filesize": MAX_FILE_BYTES,
            "outtmpl": str(destination / "media.%(ext)s"),
        }
        if self.proxy_url:
            options["proxy"] = self.proxy_url
        try:
            with YoutubeDL(options) as downloader:
                code = downloader.download([url])
        except DownloadError as error:
            raise UrlPolicyError("This provider did not make the selected format available for download.") from error
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
        output = self.downloader.download(media["sourceUrl"], format_id, destination)
        return {
            "path": output,
            "contentType": self._content_type(allowed["container"]),
            "sizeBytes": output.stat().st_size,
            "title": media["title"],
        }

    @staticmethod
    def _content_type(container: str) -> str:
        return {"mp4": "video/mp4", "webm": "video/webm", "mkv": "video/x-matroska"}.get(container, "application/octet-stream")


default_download_worker = TrialDownloadWorker(
    inspector=default_inspector,
    downloader=YtDlpFileDownloader(proxy_url=build_decodo_proxy_url()),
)
