import pytest

from media_download_service.proxy import build_decodo_proxy_url, load_proxy_configuration


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


def test_builds_a_country_scoped_custom_sticky_session():
    result = build_decodo_proxy_url(
        {
            "DECODO_USERNAME": "account",
            "DECODO_PASSWORD": "password",
            "DECODO_PROXY_COUNTRY": "us",
            "DECODO_PROXY_SESSION": "trial123",
            "DECODO_PROXY_SESSION_DURATION": "30",
        }
    )

    assert result == (
        "http://user-account-country-us-session-trial123-sessionduration-30:password"
        "@gate.decodo.com:7000"
    )


@pytest.mark.parametrize("session_id", ["contains-dash", "space here", "", "a" * 33])
def test_rejects_invalid_custom_session_ids(session_id):
    source = {
        "DECODO_USERNAME": "account",
        "DECODO_PASSWORD": "password",
        "DECODO_PROXY_SESSION": session_id,
    }
    if not session_id:
        assert build_decodo_proxy_url(source) == "http://account:password@us.decodo.com:10001"
        return

    with pytest.raises(RuntimeError, match="DECODO_PROXY_SESSION"):
        build_decodo_proxy_url(source)


def test_rejects_invalid_custom_session_duration():
    with pytest.raises(RuntimeError, match="DECODO_PROXY_SESSION_DURATION"):
        build_decodo_proxy_url(
            {
                "DECODO_USERNAME": "account",
                "DECODO_PASSWORD": "password",
                "DECODO_PROXY_SESSION": "trial123",
                "DECODO_PROXY_SESSION_DURATION": "1441",
            }
        )


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


def test_inspection_uses_decodo_but_download_is_direct_by_default():
    configuration = load_proxy_configuration(
        {"DECODO_USERNAME": "account", "DECODO_PASSWORD": "password"}
    )

    assert configuration.inspect_proxy_url == "http://account:password@us.decodo.com:10001"
    assert configuration.download_proxy_url is None
    assert configuration.allow_download_proxy_fallback is False


def test_download_proxy_fallback_requires_an_explicit_opt_in():
    configuration = load_proxy_configuration(
        {
            "DECODO_USERNAME": "account",
            "DECODO_PASSWORD": "password",
            "DOWNLOAD_PROXY_FALLBACK_ENABLED": "true",
        }
    )

    assert configuration.download_proxy_url == "http://account:password@us.decodo.com:10001"
    assert configuration.allow_download_proxy_fallback is True


def test_phase_specific_proxy_urls_are_validated():
    configuration = load_proxy_configuration(
        {
            "INSPECT_PROXY": "http://inspect:secret@sg.decodo.com:10001",
            "DOWNLOAD_PROXY": "http://download:secret@us.decodo.com:10002",
            "DOWNLOAD_PROXY_FALLBACK_ENABLED": "yes",
        }
    )

    assert configuration.inspect_proxy_url == "http://inspect:secret@sg.decodo.com:10001"
    assert configuration.download_proxy_url == "http://download:secret@us.decodo.com:10002"


def test_rejects_phase_proxy_urls_outside_decodo():
    with pytest.raises(RuntimeError, match="approved Decodo endpoint"):
        load_proxy_configuration({"INSPECT_PROXY": "http://user:secret@example.com:8080"})
