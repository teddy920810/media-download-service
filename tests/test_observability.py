import logging

from media_download_service.observability import observe_transfer


def test_observations_drop_urls_and_credentials(caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        observe_transfer(
            {
                "operation": "download",
                "route": "proxy",
                "outcome": "success",
                "sizeBytes": 42,
                "url": "https://private.example/video",
                "proxyUrl": "http://user:secret@proxy.example",
            }
        )

    message = caplog.records[-1].message
    assert '"sizeBytes":42' in message
    assert "private.example" not in message
    assert "secret" not in message
