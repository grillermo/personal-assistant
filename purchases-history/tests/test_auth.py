import io
from unittest.mock import MagicMock

import pytest
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
