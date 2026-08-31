import pytest

from media_download_service.background import MODEL_VERSION, BackgroundRemovalError, ReplicateBackgroundRemover


class FakeOutput:
    def read(self):
        return b"transparent-png"


_DEFAULT_OUTPUT = object()


class FakeClient:
    def __init__(self, output=_DEFAULT_OUTPUT):
        self.output = FakeOutput() if output is _DEFAULT_OUTPUT else output
        self.calls = []

    def run(self, model, *, input, wait):
        self.calls.append((model, input, wait))
        return self.output


def test_replicate_background_remover_uses_the_pinned_official_contract():
    client = FakeClient()
    remover = ReplicateBackgroundRemover("replicate-token", client=client)

    result = remover.remove("https://private-r2.example.test/input.png")

    assert result == b"transparent-png"
    assert client.calls == [
        (
            MODEL_VERSION,
            {
                "image": "https://private-r2.example.test/input.png",
                "format": "png",
                "reverse": False,
                "threshold": 0,
                "background_type": "rgba",
            },
            30,
        )
    ]


@pytest.mark.parametrize("output", [None, "https://replicate.delivery/output.png", b""])
def test_replicate_background_remover_rejects_incomplete_file_outputs(output):
    remover = ReplicateBackgroundRemover("replicate-token", client=FakeClient(output))

    with pytest.raises(BackgroundRemovalError, match="usable image"):
        remover.remove("https://private-r2.example.test/input.png")
