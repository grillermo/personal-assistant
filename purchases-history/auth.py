import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests

REDIRECT_URI = "https://historial-de-compras.chiq.me"
AUTH_URL = "https://auth.mercadolibre.com.mx/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
DEV_PORTAL_URL = "https://developers.mercadolibre.com.mx/en_us/application-manager"


def parse_oauth_code(path: str) -> Optional[str]:
    params = parse_qs(urlparse(path).query)
    codes = params.get("code")
    return codes[0] if codes else None


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


def run_auth() -> tuple[str, str, str]:
    """
    Console-driven OAuth flow. Prints URLs for the user to visit manually.
    Returns (app_id, secret_key, auth_code).
    """
    print("\n[1/3] Open the Mercado Libre Developer Portal and log in:")
    print(f"\n  {DEV_PORTAL_URL}\n")
    print("  Create an app with these settings:")
    print("    - Name:         anything (e.g. 'My Purchase History')")
    print(f"    - Redirect URI: {REDIRECT_URI}")
    print("    - Scopes:       read, offline_access")

    print("\n[2/3] Paste your app credentials:")
    app_id = input("  APP_ID (Client ID):      ").strip()
    secret_key = input("  SECRET_KEY (Client Secret): ").strip()

    auth_url = (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={app_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=read%20offline_access"
    )
    print("\n[3/3] Open this URL, click Authorize, then paste the redirect URL you land on:")
    print(f"\n  {auth_url}\n")

    while True:
        raw = input("  Paste redirect URL (or just the code): ").strip()
        code = parse_oauth_code(raw) or (raw if raw.startswith("TG-") else None)
        if code:
            break
        print("  Could not extract code. Paste the full URL from your browser's address bar.")

    return app_id, secret_key, code


def main() -> None:
    print("=== Mercado Libre Auth Setup ===")
    app_id, secret_key, code = run_auth()

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
