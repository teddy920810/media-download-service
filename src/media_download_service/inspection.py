from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .policy import UrlPolicyError, inspect_url
from .proxy import load_proxy_configuration


class MetadataExtractor(Protocol):
    def extract(self, url: str) -> dict[str, Any]: ...


class YtDlpMetadataExtractor:
    def __init__(self, proxy_url: str | None = None):
        self.proxy_url = proxy_url

    def extract(self, url: str) -> dict[str, Any]:
        try:
            result = self._extract(url, force_mweb=True)
        except DownloadError as error:
            if "requested format is not available" not in str(error).lower():
                raise
            result = self._extract(url, force_mweb=False)
        if not isinstance(result, dict):
            raise UrlPolicyError("The media provider did not return a video.")
        return result

    def _extract(self, url: str, *, force_mweb: bool) -> object:
        options: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "extract_flat": False,
            "socket_timeout": 20,
            "extractor_retries": 2,
        }
        if force_mweb:
            options["extractor_args"] = {"youtube": {"player_client": ["mweb"]}}
        if self.proxy_url:
            options["proxy"] = self.proxy_url
        with YoutubeDL(options) as downloader:
            return downloader.extract_info(url, download=False)


@dataclass(frozen=True)
class MediaInspector:
    extractor: MetadataExtractor

    def inspect(self, raw_url: str) -> dict[str, Any]:
        accepted = inspect_url(raw_url)
        metadata = self.extractor.extract(accepted.url)
        self._validate_metadata(metadata)
        formats = self._formats(metadata)
        if not formats:
            raise UrlPolicyError("No downloadable media format is available for this link.")

        return {
            "platform": accepted.platform,
            "sourceUrl": accepted.url,
            "title": self._text(metadata.get("title"), "Untitled video"),
            "thumbnail": self._optional_text(metadata.get("thumbnail")),
            "durationSeconds": self._duration(metadata.get("duration")),
            "formats": formats,
        }

    @staticmethod
    def _text(value: object, fallback: str) -> str:
        return value.strip() if isinstance(value, str) and value.strip() else fallback

    @staticmethod
    def _optional_text(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _duration(value: object) -> int | None:
        return int(value) if isinstance(value, (int, float)) and value > 0 else None

    @staticmethod
    def _validate_metadata(metadata: dict[str, Any]) -> None:
        if metadata.get("is_live"):
            raise UrlPolicyError("Live streams are not available in the free trial.")

    @staticmethod
    def _formats(metadata: dict[str, Any]) -> list[dict[str, Any]]:
        available: list[dict[str, Any]] = []
        for source in metadata.get("formats", []):
            if not isinstance(source, dict):
                continue
            has_video = source.get("vcodec") not in (None, "none")
            has_audio = source.get("acodec") not in (None, "none")
            if not has_video and not has_audio:
                continue
            format_id = source.get("format_id")
            extension = source.get("ext")
            if not isinstance(format_id, str) or not isinstance(extension, str):
                continue
            height_value = source.get("height")
            height = height_value if has_video and isinstance(height_value, int) and height_value > 0 else None
            bitrate_value = source.get("abr")
            audio_bitrate = int(bitrate_value) if has_audio and isinstance(bitrate_value, (int, float)) and bitrate_value > 0 else None
            estimated_size = source.get("filesize") or source.get("filesize_approx")
            label = source.get("format_note")
            if not isinstance(label, str) or not label.strip():
                label = f"{height}p" if height else f"{audio_bitrate} kbps audio" if audio_bitrate else "Audio"
            available.append(
                {
                    "formatId": format_id,
                    "label": str(label),
                    "container": extension,
                    "height": height,
                    "hasVideo": has_video,
                    "hasAudio": has_audio,
                    "audioBitrateKbps": audio_bitrate,
                    "estimatedSizeBytes": int(estimated_size) if isinstance(estimated_size, (int, float)) else None,
                }
            )
        return sorted(
            available,
            key=lambda item: (
                item["hasVideo"],
                item["height"] or 0,
                item["hasAudio"],
                item["audioBitrateKbps"] or 0,
            ),
            reverse=True,
        )


default_inspector = MediaInspector(
    extractor=YtDlpMetadataExtractor(proxy_url=load_proxy_configuration().inspect_proxy_url)
)
