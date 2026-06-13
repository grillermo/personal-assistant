import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests
from playwright.sync_api import sync_playwright

REDIRECT_URI = "http://localhost:8080"
AUTH_URL = "https://auth.mercadolibre.com.mx/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
DEV_PORTAL_URL = "https://developers.mercadolibre.com.mx/en_us/application-manager"


def parse_oauth_code(path: str) -> Optional[str]:
    params = parse_qs(urlparse(path).query)
    codes = params.get("code")
    return codes[0] if codes else None


def make_oauth_handler(code_container: dict):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            code = parse_oauth_code(self.path)
            if code:
                code_container["code"] = code
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    b"<h1>Authorization successful!</h1><p>Return to your terminal.</p>"
                )
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Error: no code found in redirect.</h1>")

        def log_message(self, format, *args):
            pass  # suppress server log noise

    return _Handler


def start_oauth_server(code_container: dict) -> tuple[HTTPServer, threading.Thread]:
    handler_cls = make_oauth_handler(code_container)
    try:
        server = HTTPServer(("localhost", 8080), handler_cls)
    except OSError as e:
        raise RuntimeError(
            "Port 8080 is already in use. Free it with: lsof -ti:8080 | xargs kill"
        ) from e
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_oauth_server(server: HTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)
