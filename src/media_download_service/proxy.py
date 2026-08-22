from __future__ import annotations

import os
import re
from dataclasses import dataclass
from collections.abc import Mapping
from urllib.parse import quote, urlsplit


APPROVED_DECODO_HOSTS = {
    "us.decodo.com",
    "sg.decodo.com",
    "eu.decodo.com",
    "gate.decodo.com",
}

CUSTOM_SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,32}$")
COUNTRY_PATTERN = re.compile(r"^[a-z]{2}$")


@dataclass(frozen=True)
class ProxyConfiguration:
    inspect_proxy_url: str | None
    download_proxy_url: str | None
    allow_download_proxy_fallback: bool


def _configured_proxy_url(name: str, source: Mapping[str, str]) -> str | None:
    value = source.get(name, "").strip()
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in APPROVED_DECODO_HOSTS:
        raise RuntimeError(f"{name} must use an approved Decodo endpoint.")
    if not parsed.username or not parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError(f"{name} must be a credentialed proxy URL without a path, query, or fragment.")
    try:
        port = parsed.port
    except ValueError as error:
        raise RuntimeError(f"{name} must use a valid port.") from error
    if port is None:
        raise RuntimeError(f"{name} must use a valid port.")
    return value


def _enabled(name: str, source: Mapping[str, str]) -> bool:
    value = source.get(name, "false").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise RuntimeError(f"{name} must be true or false.")


def load_proxy_configuration(source: Mapping[str, str] = os.environ) -> ProxyConfiguration:
    shared_decodo_url = build_decodo_proxy_url(source)
    inspect_proxy_url = _configured_proxy_url("INSPECT_PROXY", source) or shared_decodo_url
    allow_fallback = _enabled("DOWNLOAD_PROXY_FALLBACK_ENABLED", source)
    configured_download_url = _configured_proxy_url("DOWNLOAD_PROXY", source)
    download_proxy_url = configured_download_url or (shared_decodo_url if allow_fallback else None)
    return ProxyConfiguration(inspect_proxy_url, download_proxy_url, allow_fallback)


def build_decodo_proxy_url(source: Mapping[str, str] = os.environ) -> str | None:
    username = source.get("DECODO_USERNAME", "").strip()
    password = source.get("DECODO_PASSWORD", "").strip()
    if not username and not password:
        return None
    if not username or not password:
        raise RuntimeError("DECODO_USERNAME and DECODO_PASSWORD must be configured together.")

    session_id = source.get("DECODO_PROXY_SESSION", "").strip()
    if session_id:
        if not CUSTOM_SESSION_PATTERN.fullmatch(session_id):
            raise RuntimeError("DECODO_PROXY_SESSION must contain 1-32 letters, digits, or underscores.")
        country = source.get("DECODO_PROXY_COUNTRY", "us").strip().lower()
        if not COUNTRY_PATTERN.fullmatch(country):
            raise RuntimeError("DECODO_PROXY_COUNTRY must be a two-letter country code.")
        raw_duration = source.get("DECODO_PROXY_SESSION_DURATION", "30").strip()
        try:
            duration = int(raw_duration)
        except ValueError as error:
            raise RuntimeError("DECODO_PROXY_SESSION_DURATION must be between 1 and 1440 minutes.") from error
        if not 1 <= duration <= 1440:
            raise RuntimeError("DECODO_PROXY_SESSION_DURATION must be between 1 and 1440 minutes.")

        username = (
            f"user-{username}-country-{country}-session-{session_id}"
            f"-sessionduration-{duration}"
        )
        host = "gate.decodo.com"
        port = 7000
        encoded_username = quote(username, safe="")
        encoded_password = quote(password, safe="")
        return f"http://{encoded_username}:{encoded_password}@{host}:{port}"

    host = source.get("DECODO_PROXY_HOST", "us.decodo.com").strip().lower()
    if host not in APPROVED_DECODO_HOSTS:
        raise RuntimeError("DECODO_PROXY_HOST must be an approved Decodo endpoint.")

    raw_port = source.get("DECODO_PROXY_PORT", "10001").strip()
    try:
        port = int(raw_port)
    except ValueError as error:
        raise RuntimeError("DECODO_PROXY_PORT must be a valid port.") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("DECODO_PROXY_PORT must be a valid port.")

    encoded_username = quote(username, safe="")
    encoded_password = quote(password, safe="")
    return f"http://{encoded_username}:{encoded_password}@{host}:{port}"
