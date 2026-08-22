from __future__ import annotations

import json
import logging
from collections.abc import Mapping


LOGGER = logging.getLogger("uvicorn.error")


def observe_transfer(event: Mapping[str, object]) -> None:
    """Emit aggregate-friendly fields without source URLs or proxy credentials."""
    allowed = {"operation", "route", "outcome", "retryable", "sizeBytes", "attempt"}
    payload = {key: value for key, value in event.items() if key in allowed}
    LOGGER.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))
