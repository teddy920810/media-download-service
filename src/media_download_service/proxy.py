from __future__ import annotations

import os
import re
from collections.abc import Mapping
from urllib.parse import quote


APPROVED_DECODO_HOSTS = {
    "us.decodo.com",
    "sg.decodo.com",
    "eu.decodo.com",
    "gate.decodo.com",
}

CUSTOM_SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,32}$")
COUNTRY_PATTERN = re.compile(r"^[a-z]{2}$")


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
