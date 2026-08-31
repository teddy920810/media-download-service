from __future__ import annotations

from typing import Protocol

import replicate


MODEL_VERSION = (
    "851-labs/background-remover:"
    "a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc"
)


class BackgroundRemovalError(RuntimeError):
    pass


class ReplicateClient(Protocol):
    def run(self, model: str, *, input: dict[str, object], wait: int) -> object: ...


class ReplicateBackgroundRemover:
    def __init__(self, api_token: str, client: ReplicateClient | None = None):
        self.client = client or replicate.Client(api_token=api_token)

    def remove(self, input_url: str) -> bytes:
        output = self.client.run(
            MODEL_VERSION,
            input={
                "image": input_url,
                "format": "png",
                "reverse": False,
                "threshold": 0,
                "background_type": "rgba",
            },
            wait=30,
        )
        if isinstance(output, list):
            output = output[0] if output else None
        reader = getattr(output, "read", None)
        if not callable(reader):
            raise BackgroundRemovalError("Replicate did not return a usable image file.")
        content = reader()
        if not isinstance(content, bytes) or not content:
            raise BackgroundRemovalError("Replicate did not return a usable image file.")
        return content
