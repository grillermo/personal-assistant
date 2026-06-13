import json
import time
from unittest.mock import patch, MagicMock


def _write_fixtures(tmp_path):
    """Write minimal credentials.json and tokens.json to tmp_path."""
    creds = {"app_id": "APP1", "secret_key": "SECRET1"}
    tokens = {
        "access_token": "AT-initial",
        "refresh_token": "RT-initial",
        "expires_in": 21600,
    }
    (tmp_path / "credentials.json").write_text(json.dumps(creds))
    (tmp_path / "tokens.json").write_text(json.dumps(tokens))
    return str(tmp_path / "tokens.json"), str(tmp_path / "credentials.json")


def test_get_returns_json_on_200(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": 42}
    mock_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", return_value=mock_resp):
        result = client.get("https://api.mercadolibre.com/users/me")

    assert result == {"id": 42}


def test_get_retries_on_429(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "1"}

    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"ok": True}
    ok.raise_for_status = MagicMock()

    with patch("extract.requests.get", side_effect=[rate_limited, ok]):
        with patch("extract.time.sleep"):
            result = client.get("https://example.com")

    assert result == {"ok": True}


def test_get_refreshes_on_401(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    unauthorized = MagicMock()
    unauthorized.status_code = 401

    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"refreshed": True}
    ok.raise_for_status = MagicMock()

    refresh_resp = MagicMock()
    refresh_resp.json.return_value = {
        "access_token": "AT-new",
        "refresh_token": "RT-new",
        "expires_in": 21600,
    }
    refresh_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", side_effect=[unauthorized, ok]):
        with patch("extract.requests.post", return_value=refresh_resp):
            result = client.get("https://example.com")

    assert result == {"refreshed": True}


def test_refresh_at_computed_from_expires_in(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient

    before = time.time()
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)
    after = time.time()

    expected_min = before + 21600 - 300
    expected_max = after + 21600 - 300
    assert expected_min <= client._refresh_at <= expected_max
