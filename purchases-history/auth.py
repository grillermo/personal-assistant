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


def exchange_code_for_tokens(app_id: str, secret_key: str, code: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": secret_key,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    response.raise_for_status()
    return response.json()


def save_credentials(app_id: str, secret_key: str, path: str = "credentials.json") -> None:
    Path(path).write_text(json.dumps({"app_id": app_id, "secret_key": secret_key}, indent=2))


def save_tokens(tokens: dict, path: str = "tokens.json") -> None:
    Path(path).write_text(json.dumps(tokens, indent=2))


def _scrape_text_by_selectors(page, selectors: list[str]) -> Optional[str]:
    """Try each CSS/text selector, return first visible inner text."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                return el.inner_text().strip()
        except Exception:
            continue
    return None


def _create_app_automated(page) -> tuple[str, str]:
    """
    Attempt to automate ML developer app creation.
    Falls back to manual prompts if the UI is unrecognized.
    Returns (app_id, secret_key).
    """
    try:
        btn = page.get_by_role("button", name=["Create Application", "Nueva Aplicación"]).first
        if btn.is_visible(timeout=3000):
            btn.click()
            page.locator('[name="name"], [placeholder*="name"], [placeholder*="nombre"]').first.fill(
                "My Purchase History"
            )
            page.locator('[name="redirect_uri"], [placeholder*="redirect"]').first.fill(REDIRECT_URI)
            page.get_by_role("button", name=["Save", "Guardar"]).first.click()
            page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass  # UI not recognized — fall through to manual

    print("\n   If no app exists yet, create one with these exact settings:")
    print("   - Name: anything (e.g. 'My Purchase History')")
    print(f"   - Redirect URI: {REDIRECT_URI}")
    print("   - Scopes: read, offline_access")
    input("\n>> After the app is visible on screen, press ENTER: ")

    # Try to scrape credentials from page DOM
    app_id = _scrape_text_by_selectors(page, [
        "[data-testid='app-id']", ".app-id", "#client_id", "[class*='app_id']",
    ])
    secret_key = _scrape_text_by_selectors(page, [
        "[data-testid='secret-key']", ".secret-key", "#client_secret", "[class*='secret']",
    ])

    if app_id and secret_key:
        print(f"   Auto-captured: APP_ID={app_id}")
        return app_id, secret_key

    # Manual fallback
    print("\nCould not auto-capture credentials. Please copy them from the page:")
    app_id = input("APP_ID (Client ID): ").strip()
    secret_key = input("SECRET_KEY (Client Secret): ").strip()
    return app_id, secret_key


def run_browser_auth() -> tuple[str, str, str]:
    """
    Full browser-driven OAuth flow.
    Returns (app_id, secret_key, auth_code).
    """
    code_container: dict = {}
    server, thread = start_oauth_server(code_container)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            print("\n[1/4] Opening Mercado Libre Developer Portal...")
            print("      Please log in. Complete 2FA if prompted.")
            page.goto(DEV_PORTAL_URL, wait_until="domcontentloaded")
            input("\n>> Press ENTER once you are fully logged in: ")

            print("\n[2/4] Navigating to app creation...")
            app_id, secret_key = _create_app_automated(page)

            print(f"\n[3/4] Credentials captured (APP_ID={app_id})")
            print("      Opening OAuth authorization page — click 'Authorize'.")

            auth_url = (
                f"{AUTH_URL}?response_type=code"
                f"&client_id={app_id}"
                f"&redirect_uri={REDIRECT_URI}"
                f"&scope=read%20offline_access"
            )
            page.goto(auth_url, wait_until="domcontentloaded")

            print("\n[4/4] Waiting for you to click Authorize (5-minute timeout)...")
            deadline = time.time() + 300
            while "code" not in code_container:
                if time.time() > deadline:
                    raise RuntimeError(
                        "Timed out waiting for OAuth callback. "
                        "Did you click Authorize in the browser?"
                    )
                time.sleep(0.3)

            print("      Authorization code captured!")
            browser.close()
    finally:
        stop_oauth_server(server, thread)

    return app_id, secret_key, code_container["code"]


def main() -> None:
    print("=== Mercado Libre Auth Setup ===\n")
    app_id, secret_key, code = run_browser_auth()

    print("\nExchanging authorization code for tokens...")
    tokens = exchange_code_for_tokens(app_id, secret_key, code)

    save_credentials(app_id, secret_key)
    save_tokens(tokens)

    expires_h = tokens.get("expires_in", 21600) // 3600
    print(f"\nSetup complete!")
    print(f"  credentials.json — saved")
    print(f"  tokens.json      — saved (token valid ~{expires_h}h)")
    print(f"\nNext: python extract.py")


if __name__ == "__main__":
    main()
