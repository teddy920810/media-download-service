from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from yt_dlp import YoutubeDL

from .policy import MAX_DURATION_SECONDS, MAX_FILE_BYTES, MAX_HEIGHT, UrlPolicyError, inspect_url
from .proxy import build_decodo_proxy_url


class MetadataExtractor(Protocol):
    def extract(self, url: str) -> dict[str, Any]: ...


class YtDlpMetadataExtractor:
    def __init__(self, proxy_url: str | None = None):
        self.proxy_url = proxy_url

    def extract(self, url: str) -> dict[str, Any]:
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "extract_flat": False,
        }
        if self.proxy_url:
            options["proxy"] = self.proxy_url
        with YoutubeDL(options) as downloader:
            result = downloader.extract_info(url, download=False)
        if not isinstance(result, dict):
            raise UrlPolicyError("The media provider did not return a video.")
        return result


@dataclass(frozen=True)
class MediaInspector:
    extractor: MetadataExtractor

    def inspect(self, raw_url: str) -> dict[str, Any]:
        accepted = inspect_url(raw_url)
        metadata = self.extractor.extract(accepted.url)
        self._validate_metadata(metadata)
        formats = self._formats(metadata)
        if not formats:
            raise UrlPolicyError("No trial-eligible video format is available for this link.")

        return {
            "platform": accepted.platform,
            "sourceUrl": accepted.url,
            "title": self._text(metadata.get("title"), "Untitled video"),
            "thumbnail": self._optional_text(metadata.get("thumbnail")),
            "durationSeconds": int(metadata["duration"]),
            "formats": formats,
        }

    @staticmethod
    def _text(value: object, fallback: str) -> str:
        return value.strip() if isinstance(value, str) and value.strip() else fallback

    @staticmethod
    def _optional_text(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _validate_metadata(metadata: dict[str, Any]) -> None:
        if metadata.get("is_live"):
            raise UrlPolicyError("Live streams are not available in the free trial.")
        duration = metadata.get("duration")
        if not isinstance(duration, (int, float)) or duration <= 0:
            raise UrlPolicyError("This video does not have a supported duration.")
        if duration > MAX_DURATION_SECONDS:
            raise UrlPolicyError("Free-trial videos must be 10 minutes or shorter.")

    @staticmethod
    def _formats(metadata: dict[str, Any]) -> list[dict[str, Any]]:
        eligible: list[dict[str, Any]] = []
        for source in metadata.get("formats", []):
            if not isinstance(source, dict) or source.get("vcodec") in (None, "none"):
                continue
            height = source.get("height")
            if not isinstance(height, int) or not 0 < height <= MAX_HEIGHT:
                continue
            format_id = source.get("format_id")
            extension = source.get("ext")
            if not isinstance(format_id, str) or not isinstance(extension, str):
                continue
            estimated_size = source.get("filesize") or source.get("filesize_approx")
            if isinstance(estimated_size, (int, float)) and estimated_size > MAX_FILE_BYTES:
                continue
            has_audio = source.get("acodec") not in (None, "none")
            label = source.get("format_note") or f"{height}p"
            eligible.append(
                {
                    "formatId": format_id,
                    "label": str(label),
                    "container": extension,
                    "height": height,
                    "hasAudio": has_audio,
                    "estimatedSizeBytes": int(estimated_size) if isinstance(estimated_size, (int, float)) else None,
                }
            )
        return sorted(eligible, key=lambda item: (item["height"], item["hasAudio"]), reverse=True)


default_inspector = MediaInspector(extractor=YtDlpMetadataExtractor(proxy_url=build_decodo_proxy_url()))
