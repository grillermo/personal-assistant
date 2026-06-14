import json
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv()

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


def start_oauth_server(host: str, port: int, code_container: dict) -> tuple[HTTPServer, threading.Thread]:
    handler_cls = make_oauth_handler(code_container)
    try:
        server = HTTPServer((host, port), handler_cls)
    except OSError as e:
        raise RuntimeError(
            f"Port {port} is already in use. Free it with: lsof -ti:{port} | xargs kill"
        ) from e
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_oauth_server(server: HTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)


def exchange_code_for_tokens(app_id: str, secret_key: str, code: str, redirect_uri: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": secret_key,
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    response.raise_for_status()
    return response.json()


def save_credentials(app_id: str, secret_key: str, path: str = "credentials.json") -> None:
    Path(path).write_text(json.dumps({"app_id": app_id, "secret_key": secret_key}, indent=2))


def save_tokens(tokens: dict, path: str = "tokens.json") -> None:
    Path(path).write_text(json.dumps(tokens, indent=2))


def run_auth() -> tuple[str, str, str]:
    """
    OAuth flow. Reads credentials from .env. Starts a local callback server when
    the redirect URI points at localhost; otherwise falls back to manual paste.
    Returns (app_id, secret_key, auth_code).
    """
    app_id = os.getenv("MELI_CLIENT_ID")
    secret_key = os.getenv("MELI_CLIENT_SECRET")
    redirect_uri = os.getenv("MELI_REDIRECT_URI")

    if not app_id or not secret_key or not redirect_uri:
        raise ValueError("Missing required .env vars: MELI_CLIENT_ID, MELI_CLIENT_SECRET, MELI_REDIRECT_URI")

    print("\n[1/2] Loaded credentials from .env")
    print(f"  App ID:       {app_id}")
    print(f"  Redirect URI: {redirect_uri}")
    print("  Scopes:       read, offline_access")

    auth_url = (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={app_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read%20offline_access"
    )

    # redirect_uri is the public URL ML calls (e.g. a Cloudflare tunnel);
    # the tunnel forwards to a local server on MELI_CALLBACK_PORT.
    port = int(os.getenv("MELI_CALLBACK_PORT", "8080"))
    code_container: dict = {}
    server, thread = start_oauth_server("localhost", port, code_container)
    try:
        print("\n[2/2] Open this URL and click Authorize:")
        print(f"\n  {auth_url}\n")
        print(f"  Waiting for callback on localhost:{port} (5-minute timeout)...")
        deadline = time.time() + 300
        while "code" not in code_container:
            if time.time() > deadline:
                raise RuntimeError(
                    "Timed out waiting for OAuth callback. Did you click Authorize?"
                )
            time.sleep(0.3)
        print("  Authorization code captured!")
        code = code_container["code"]
    finally:
        stop_oauth_server(server, thread)

    return app_id, secret_key, code


def main() -> None:
    print("=== Mercado Libre Auth Setup ===")
    app_id, secret_key, code = run_auth()
    redirect_uri = os.getenv("MELI_REDIRECT_URI")

    print("\nExchanging authorization code for tokens...")
    tokens = exchange_code_for_tokens(app_id, secret_key, code, redirect_uri)

    save_credentials(app_id, secret_key)
    save_tokens(tokens)

    expires_h = tokens.get("expires_in", 21600) // 3600
    print(f"\nSetup complete!")
    print(f"  credentials.json — saved")
    print(f"  tokens.json      — saved (token valid ~{expires_h}h)")
    print(f"\nNext: python extract.py")


if __name__ == "__main__":
    main()
