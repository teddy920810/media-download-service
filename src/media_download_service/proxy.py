from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import quote


APPROVED_DECODO_HOSTS = {
    "us.decodo.com",
    "sg.decodo.com",
    "eu.decodo.com",
    "gate.decodo.com",
}


def build_decodo_proxy_url(source: Mapping[str, str] = os.environ) -> str | None:
    username = source.get("DECODO_USERNAME", "").strip()
    password = source.get("DECODO_PASSWORD", "").strip()
    if not username and not password:
        return None
    if not username or not password:
        raise RuntimeError("DECODO_USERNAME and DECODO_PASSWORD must be configured together.")

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
