import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from auth import (
    exchange_code_for_tokens,
    parse_oauth_code,
    save_credentials,
    save_tokens,
)


def test_parse_oauth_code_with_valid_code():
    assert parse_oauth_code("/?code=TG-abc123") == "TG-abc123"


def test_parse_oauth_code_missing_code_returns_none():
    assert parse_oauth_code("/") is None


def test_parse_oauth_code_empty_path_returns_none():
    assert parse_oauth_code("") is None


def test_parse_oauth_code_other_params_ignored():
    assert parse_oauth_code("/?state=xyz&code=TG-abc123&foo=bar") == "TG-abc123"


def test_parse_oauth_code_full_redirect_url():
    url = "https://historial-de-compras.chiq.me/?code=TG-xyz99&state=abc"
    assert parse_oauth_code(url) == "TG-xyz99"


def test_exchange_code_posts_correct_payload():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "access_token": "AT-abc",
        "refresh_token": "RT-xyz",
        "expires_in": 21600,
    }
    with patch("auth.requests.post", return_value=mock_resp) as mock_post:
        result = exchange_code_for_tokens("APP1", "SECRET1", "CODE1")

    posted_data = mock_post.call_args.kwargs["data"]
    assert posted_data["grant_type"] == "authorization_code"
    assert posted_data["client_id"] == "APP1"
    assert posted_data["code"] == "CODE1"
    assert result["access_token"] == "AT-abc"
    mock_resp.raise_for_status.assert_called_once()


def test_save_credentials_writes_json(tmp_path):
    path = str(tmp_path / "creds.json")
    save_credentials("MY_APP", "MY_SECRET", path)
    data = json.loads(Path(path).read_text())
    assert data == {"app_id": "MY_APP", "secret_key": "MY_SECRET"}


def test_save_tokens_writes_json(tmp_path):
    path = str(tmp_path / "tokens.json")
    tokens = {"access_token": "AT", "refresh_token": "RT", "expires_in": 21600}
    save_tokens(tokens, path)
    data = json.loads(Path(path).read_text())
    assert data == tokens
