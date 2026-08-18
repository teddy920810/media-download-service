import pytest

from media_download_service.proxy import build_decodo_proxy_url


def test_builds_an_encoded_http_proxy_url():
    result = build_decodo_proxy_url(
        {
            "DECODO_USERNAME": "account user",
            "DECODO_PASSWORD": "pass@word:with/slash",
            "DECODO_PROXY_HOST": "us.decodo.com",
            "DECODO_PROXY_PORT": "10001",
        }
    )

    assert result == "http://account%20user:pass%40word%3Awith%2Fslash@us.decodo.com:10001"


def test_proxy_is_optional_for_local_development():
    assert build_decodo_proxy_url({}) is None


def test_rejects_partial_proxy_credentials():
    with pytest.raises(RuntimeError, match="DECODO_USERNAME and DECODO_PASSWORD"):
        build_decodo_proxy_url({"DECODO_USERNAME": "account"})


@pytest.mark.parametrize("host", ["example.com", "us.decodo.com.attacker.test", "127.0.0.1"])
def test_rejects_untrusted_proxy_hosts(host):
    with pytest.raises(RuntimeError, match="approved Decodo endpoint"):
        build_decodo_proxy_url(
            {
                "DECODO_USERNAME": "account",
                "DECODO_PASSWORD": "password",
                "DECODO_PROXY_HOST": host,
            }
        )
