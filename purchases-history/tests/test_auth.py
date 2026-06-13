import io
from unittest.mock import MagicMock

from auth import parse_oauth_code, make_oauth_handler, start_oauth_server, stop_oauth_server


def test_parse_oauth_code_with_valid_code():
    assert parse_oauth_code("/?code=TG-abc123") == "TG-abc123"


def test_parse_oauth_code_missing_code_returns_none():
    assert parse_oauth_code("/") is None


def test_parse_oauth_code_empty_path_returns_none():
    assert parse_oauth_code("") is None


def test_parse_oauth_code_other_params_ignored():
    assert parse_oauth_code("/?state=xyz&code=TG-abc123&foo=bar") == "TG-abc123"


def _make_request(handler_class, path):
    """Simulate an HTTP GET to the handler."""
    code_container = {}
    # handler_class is a factory that takes code_container
    # We test the handler behavior via its do_GET method
    # Build the factory result
    handler_cls = handler_class(code_container)

    handler = handler_cls.__new__(handler_cls)
    handler.path = path
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.end_headers = MagicMock()

    return handler, code_container


def test_oauth_handler_captures_code():
    handler, code_container = _make_request(make_oauth_handler, "/?code=TG-abc123")
    handler.do_GET()
    assert code_container["code"] == "TG-abc123"
    handler.send_response.assert_called_once_with(200)


def test_oauth_handler_bad_request_on_missing_code():
    handler, code_container = _make_request(make_oauth_handler, "/")
    handler.do_GET()
    assert "code" not in code_container
    handler.send_response.assert_called_once_with(400)


def test_start_stop_server_lifecycle():
    code_container = {}
    server, thread = start_oauth_server(code_container)
    assert thread.is_alive()
    stop_oauth_server(server, thread)
    assert not thread.is_alive()


import json
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path
from auth import exchange_code_for_tokens, save_credentials, save_tokens


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
