# Mercado Libre Purchase History Extractor — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce two Python scripts — `auth.py` (Playwright OAuth flow) and `extract.py` (API pagination + CSV export) — that together retrieve and export a complete Mercado Libre Mexico purchase history.

**Architecture:** `auth.py` drives a non-headless Chromium browser to create an ML developer app, run the OAuth authorization code flow via a background HTTP server on `:8080`, and persist `credentials.json` + `tokens.json`. `extract.py` reads those files, uses a thread-safe `MeliClient` with auto-refresh, paginates all buyer orders, batch-hydrates item details, and exports to CSV via pandas.

**Tech Stack:** Python 3.11+, Playwright (sync API), requests, pandas, pytest, unittest.mock

---

## Chunk 1: Scaffold + auth.py

### Task 1: Project scaffold

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `.gitignore`**

```
credentials.json
tokens.json
*.csv
__pycache__/
.pytest_cache/
*.pyc
.venv/
```

- [ ] **Step 2: Create `requirements.txt`**

```
playwright>=1.40.0
requests>=2.31.0
pandas>=2.1.0
pytest>=8.0.0
```

- [ ] **Step 3: Create `tests/__init__.py`** (empty file)

- [ ] **Step 4: Commit**

```bash
git add .gitignore requirements.txt tests/__init__.py
git commit -m "chore: scaffold project with deps and gitignore"
```

---

### Task 2: `parse_oauth_code` — pure helper with tests

**Files:**
- Create: `auth.py` (initial — just the pure helper + imports)
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_auth.py`:
```python
import pytest
from auth import parse_oauth_code


def test_parse_oauth_code_with_valid_code():
    assert parse_oauth_code("/?code=TG-abc123") == "TG-abc123"


def test_parse_oauth_code_missing_code_returns_none():
    assert parse_oauth_code("/") is None


def test_parse_oauth_code_empty_path_returns_none():
    assert parse_oauth_code("") is None


def test_parse_oauth_code_other_params_ignored():
    assert parse_oauth_code("/?state=xyz&code=TG-abc123&foo=bar") == "TG-abc123"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_auth.py -v
```
Expected: `ModuleNotFoundError: No module named 'auth'`

- [ ] **Step 3: Create `auth.py` with `parse_oauth_code`**

```python
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_auth.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_auth.py
git commit -m "feat: add parse_oauth_code with tests"
```

---

### Task 3: OAuth callback server

**Files:**
- Modify: `auth.py` (append `make_oauth_handler`, `start_oauth_server`, `stop_oauth_server`)
- Modify: `tests/test_auth.py` (append server tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_auth.py`:
```python
import io
from unittest.mock import MagicMock, patch
from auth import make_oauth_handler, start_oauth_server, stop_oauth_server


def _make_request(handler_class, path):
    """Simulate an HTTP GET to the handler."""
    code_container = {}
    # handler_class is a factory that takes code_container
    # We test the handler behavior via its do_GET method
    # Build the factory result
    handler_cls = handler_class(code_container)

    mock_request = MagicMock()
    mock_request.makefile.return_value = io.BytesIO(
        f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
    )
    mock_server = MagicMock()

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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_auth.py::test_oauth_handler_captures_code -v
```
Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: Implement server functions in `auth.py`**

Append to `auth.py` after `parse_oauth_code`:
```python
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

        def log_message(self, *args):
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_auth.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_auth.py
git commit -m "feat: OAuth callback server with start/stop lifecycle"
```

---

### Task 4: Token exchange + credential persistence

**Files:**
- Modify: `auth.py` (append `exchange_code_for_tokens`, `save_credentials`, `save_tokens`)
- Modify: `tests/test_auth.py` (append token tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_auth.py`:
```python
import json
import tempfile
from unittest.mock import patch, MagicMock
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_auth.py::test_exchange_code_posts_correct_payload -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement in `auth.py`**

Append to `auth.py`:
```python
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_auth.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_auth.py
git commit -m "feat: token exchange and credential persistence"
```

---

### Task 5: Browser automation + `main()` in auth.py

**Files:**
- Modify: `auth.py` (append `_scrape_credential`, `_create_app_automated`, `run_browser_auth`, `main`)

No unit tests for the Playwright functions (browser interaction requires integration testing). The pure helpers are already tested.

- [ ] **Step 1: Append browser functions to `auth.py`**

```python
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
```

- [ ] **Step 2: Run full test suite to verify nothing broken**

```bash
pytest tests/ -v
```
Expected: all existing tests pass

- [ ] **Step 3: Commit**

```bash
git add auth.py
git commit -m "feat: browser automation and auth.py main() entry point"
```

---

## Chunk 2: extract.py + SETUP.md

### Task 6: `MeliClient` core — get() with retry and token refresh

**Files:**
- Create: `extract.py`
- Create: `tests/test_extract.py`

- [ ] **Step 1: Write failing tests**

`tests/test_extract.py`:
```python
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call


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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_extract.py -v
```
Expected: `ModuleNotFoundError: No module named 'extract'`

- [ ] **Step 3: Create `extract.py` with `MeliClient`**

```python
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

API_BASE = "https://api.mercadolibre.com"
TOKEN_URL = f"{API_BASE}/oauth/token"


class MeliClient:
    def __init__(
        self,
        tokens_path: str = "tokens.json",
        creds_path: str = "credentials.json",
    ):
        self._lock = threading.Lock()
        self._tokens_path = tokens_path
        self._tokens = json.loads(Path(tokens_path).read_text())
        self._creds = json.loads(Path(creds_path).read_text())
        self._refresh_at = time.time() + self._tokens.get("expires_in", 21600) - 300
        self._start_refresh_thread()

    def _start_refresh_thread(self) -> None:
        def loop():
            while True:
                sleep_for = max(0, self._refresh_at - time.time())
                time.sleep(sleep_for)
                self._refresh_token()

        threading.Thread(target=loop, daemon=True).start()

    def _refresh_token(self) -> None:
        print("\n[Token] Refreshing...")
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self._creds["app_id"],
                "client_secret": self._creds["secret_key"],
                "refresh_token": self._tokens["refresh_token"],
            },
        )
        resp.raise_for_status()
        new_tokens = resp.json()
        with self._lock:
            self._tokens = new_tokens
            self._refresh_at = time.time() + new_tokens.get("expires_in", 21600) - 300
            Path(self._tokens_path).write_text(json.dumps(new_tokens, indent=2))
        print("[Token] Refreshed.")

    def _headers(self) -> dict:
        with self._lock:
            return {"Authorization": f"Bearer {self._tokens['access_token']}"}

    def get(self, url: str, params: dict = None, retries: int = 3) -> dict | list:
        for attempt in range(retries):
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 5))
                print(f"[Rate limit] Waiting {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 401:
                print("[Auth] Token expired mid-run, refreshing...")
                self._refresh_token()
                continue
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError:
                if attempt == retries - 1:
                    raise
                time.sleep(2**attempt)
                continue
            return resp.json()
        raise RuntimeError(f"Failed after {retries} retries: {url}")

    def get_user_id(self) -> int:
        return self.get(f"{API_BASE}/users/me")["id"]
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_extract.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: MeliClient with thread-safe get(), retry, and auto token refresh"
```

---

### Task 7: Order pagination

**Files:**
- Modify: `extract.py` (add `get_all_orders` to `MeliClient`)
- Modify: `tests/test_extract.py` (append pagination tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_extract.py`:
```python
def test_get_all_orders_paginates(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = {
        "results": [{"id": f"order_{i}"} for i in range(50)],
        "paging": {"total": 75, "offset": 0, "limit": 50},
    }
    page1.raise_for_status = MagicMock()

    page2 = MagicMock()
    page2.status_code = 200
    page2.json.return_value = {
        "results": [{"id": f"order_{i}"} for i in range(50, 75)],
        "paging": {"total": 75, "offset": 50, "limit": 50},
    }
    page2.raise_for_status = MagicMock()

    with patch("extract.requests.get", side_effect=[page1, page2]):
        with patch("extract.time.sleep"):
            orders = client.get_all_orders(user_id=123456)

    assert len(orders) == 75
    assert orders[0]["id"] == "order_0"
    assert orders[74]["id"] == "order_74"


def test_get_all_orders_stops_on_empty_results(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    empty_resp = MagicMock()
    empty_resp.status_code = 200
    empty_resp.json.return_value = {
        "results": [],
        "paging": {"total": 0},
    }
    empty_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", return_value=empty_resp):
        orders = client.get_all_orders(user_id=123456)

    assert orders == []
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_extract.py::test_get_all_orders_paginates -v
```
Expected: `AttributeError: 'MeliClient' object has no attribute 'get_all_orders'`

- [ ] **Step 3: Add `get_all_orders` to `MeliClient` in `extract.py`**

Add inside the `MeliClient` class, after `get_user_id`:
```python
    def get_all_orders(self, user_id: int) -> list[dict]:
        orders: list[dict] = []
        offset = 0
        limit = 50

        while True:
            print(f"  Fetching orders {offset}–{offset + limit}...")
            data = self.get(
                f"{API_BASE}/orders/search",
                params={"buyer": user_id, "offset": offset, "limit": limit},
            )
            results = data.get("results", [])
            total = data.get("paging", {}).get("total", 0)
            orders.extend(results)
            offset += len(results)
            print(f"  Progress: {len(orders)}/{total}")

            if not results or offset >= total:
                break
            time.sleep(0.5)

        return orders
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_extract.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: order pagination with offset loop"
```

---

### Task 8: Item hydration

**Files:**
- Modify: `extract.py` (add module-level `collect_item_ids`, `MeliClient.hydrate_items`)
- Modify: `tests/test_extract.py` (append hydration tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_extract.py`:
```python
def test_collect_item_ids_splits_by_title_presence():
    from extract import collect_item_ids
    orders = [
        {
            "order_items": [
                {"item": {"id": "MLA1", "title": "Laptop"}},
                {"item": {"id": "MLA2", "title": ""}},
                {"item": {"id": "MLA3"}},
            ]
        }
    ]
    all_ids, has_title = collect_item_ids(orders)  # noqa: F821 — imported above
    assert set(all_ids) == {"MLA1", "MLA2", "MLA3"}
    assert has_title == {"MLA1"}


def test_hydrate_items_filters_non_200(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    batch_resp = MagicMock()
    batch_resp.status_code = 200
    batch_resp.json.return_value = [
        {"code": 200, "body": {"id": "MLA1", "title": "Good Item", "category_id": "MLA1055"}},
        {"code": 404, "body": {"id": "MLA2", "message": "Item not found"}},
    ]
    batch_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", return_value=batch_resp):
        result = client.hydrate_items(["MLA1", "MLA2"])

    assert "MLA1" in result
    assert result["MLA1"]["title"] == "Good Item"
    assert "MLA2" not in result


def test_hydrate_items_deduplicates_ids(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    batch_resp = MagicMock()
    batch_resp.status_code = 200
    batch_resp.json.return_value = [
        {"code": 200, "body": {"id": "MLA1", "title": "Item", "category_id": "CAT1"}},
    ]
    batch_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", return_value=batch_resp) as mock_get:
        client.hydrate_items(["MLA1", "MLA1", "MLA1"])

    # Only one batch call for one unique ID
    assert mock_get.call_count == 1
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_extract.py::test_collect_item_ids_splits_by_title_presence -v
```
Expected: `ImportError`

- [ ] **Step 3: Add `collect_item_ids` and `MeliClient.hydrate_items` to `extract.py`**

After the `MeliClient` class definition, add:
```python
def collect_item_ids(orders: list[dict]) -> tuple[list[str], set[str]]:
    all_ids: list[str] = []
    has_title: set[str] = set()
    for order in orders:
        for oi in order.get("order_items", []):
            item = oi.get("item", {})
            item_id = item.get("id")
            if item_id:
                all_ids.append(item_id)
                if item.get("title"):
                    has_title.add(item_id)
    return all_ids, has_title
```

Inside `MeliClient`, add after `get_all_orders`:
```python
    def hydrate_items(self, item_ids: list[str]) -> dict[str, dict]:
        unique_ids = list(dict.fromkeys(item_ids))  # deduplicate, preserve insertion order
        batches = [unique_ids[i : i + 20] for i in range(0, len(unique_ids), 20)]
        results: dict[str, dict] = {}

        def fetch_batch(batch: list[str]) -> dict[str, dict]:
            batch_results: dict[str, dict] = {}
            try:
                data = self.get(f"{API_BASE}/items", params={"ids": ",".join(batch)})
                for entry in data:
                    if entry.get("code") == 200:
                        body = entry.get("body", {})
                        batch_results[body["id"]] = body
            except Exception as e:
                print(f"[Warning] Batch hydration failed: {e}")
            return batch_results

        print(f"\nHydrating {len(unique_ids)} items across {len(batches)} batch(es)...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            for batch_result in executor.map(fetch_batch, batches):
                results.update(batch_result)

        return results
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_extract.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: item hydration with batch GET and 200-filter"
```

---

### Task 9: Row extraction and CSV export

**Files:**
- Modify: `extract.py` (add `extract_order_rows`, `main`)
- Modify: `tests/test_extract.py` (append row tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_extract.py`:
```python
def test_extract_order_rows_single_item():
    from extract import extract_order_rows
    order = {
        "id": "ORD1",
        "date_created": "2024-01-15T10:00:00.000Z",
        "status": "paid",
        "total_amount": 299.0,
        "currency_id": "MXN",
        "order_items": [
            {"item": {"id": "MLA1", "title": "Laptop"}, "quantity": 1, "unit_price": 299.0}
        ],
    }
    rows = extract_order_rows(order, {})
    assert len(rows) == 1
    assert rows[0]["order_id"] == "ORD1"
    assert rows[0]["item_title"] == "Laptop"
    assert rows[0]["item_quantity"] == 1
    assert rows[0]["item_unit_price"] == 299.0
    assert rows[0]["order_total_amount"] == 299.0
    assert rows[0]["currency"] == "MXN"


def test_extract_order_rows_multi_item_shares_order_total():
    from extract import extract_order_rows
    order = {
        "id": "ORD2",
        "date_created": "2024-02-01T08:00:00.000Z",
        "status": "paid",
        "total_amount": 500.0,
        "currency_id": "MXN",
        "order_items": [
            {"item": {"id": "MLA1", "title": "Book"}, "quantity": 2, "unit_price": 150.0},
            {"item": {"id": "MLA2"}, "quantity": 1, "unit_price": 200.0},
        ],
    }
    cache = {"MLA2": {"title": "Headphones", "category_id": "ELEC"}}
    rows = extract_order_rows(order, cache)

    assert len(rows) == 2
    assert rows[0]["order_id"] == rows[1]["order_id"] == "ORD2"
    assert rows[0]["order_total_amount"] == rows[1]["order_total_amount"] == 500.0
    assert rows[0]["item_title"] == "Book"
    assert rows[1]["item_title"] == "Headphones"
    assert rows[1]["item_category"] == "ELEC"


def test_extract_order_rows_no_items_produces_placeholder():
    from extract import extract_order_rows
    order = {
        "id": "ORD3",
        "date_created": "2024-03-01T00:00:00.000Z",
        "status": "cancelled",
        "total_amount": 0,
        "currency_id": "MXN",
        "order_items": [],
    }
    rows = extract_order_rows(order, {})
    assert len(rows) == 1
    assert rows[0]["item_title"] == "N/A"


def test_extract_order_rows_falls_back_to_cache_for_missing_title():
    from extract import extract_order_rows
    order = {
        "id": "ORD4",
        "date_created": "2024-04-01T00:00:00.000Z",
        "status": "paid",
        "total_amount": 100.0,
        "currency_id": "MXN",
        "order_items": [
            {"item": {"id": "MLA9"}, "quantity": 1, "unit_price": 100.0},
        ],
    }
    cache = {"MLA9": {"title": "Widget", "category_id": "TOOLS"}}
    rows = extract_order_rows(order, cache)
    assert rows[0]["item_title"] == "Widget"
    assert rows[0]["item_category"] == "TOOLS"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_extract.py::test_extract_order_rows_single_item -v
```
Expected: `ImportError`

- [ ] **Step 3: Add `extract_order_rows` and `main` to `extract.py`**

Append to `extract.py`:
```python
def extract_order_rows(order: dict, items_cache: dict) -> list[dict]:
    order_id = order.get("id")
    purchase_date = order.get("date_created", "")
    status = order.get("status", "")
    order_total = order.get("total_amount", 0)
    currency = order.get("currency_id", "")

    rows = []
    for oi in order.get("order_items", []):
        item = oi.get("item", {})
        item_id = item.get("id", "")
        cached = items_cache.get(item_id, {})
        rows.append({
            "order_id": order_id,
            "purchase_date": purchase_date,
            "status": status,
            "item_title": item.get("title") or cached.get("title", "Unknown"),
            "item_category": cached.get("category_id", "Unknown"),
            "item_quantity": oi.get("quantity", 1),
            "item_unit_price": oi.get("unit_price", 0),
            "order_total_amount": order_total,
            "currency": currency,
        })

    if not rows:
        rows.append({
            "order_id": order_id,
            "purchase_date": purchase_date,
            "status": status,
            "item_title": "N/A",
            "item_category": "N/A",
            "item_quantity": 0,
            "item_unit_price": 0,
            "order_total_amount": order_total,
            "currency": currency,
        })

    return rows


def main() -> None:
    print("=== Mercado Libre Purchase History Extractor ===\n")

    client = MeliClient()

    print("Identifying user...")
    user_id = client.get_user_id()
    print(f"User ID: {user_id}\n")

    print("Fetching all orders (this may take a while for large histories)...")
    orders = client.get_all_orders(user_id)
    print(f"\nTotal orders fetched: {len(orders)}")

    all_ids, has_title = collect_item_ids(orders)
    ids_to_fetch = [i for i in dict.fromkeys(all_ids) if i not in has_title]
    items_cache: dict = {}
    if ids_to_fetch:
        items_cache = client.hydrate_items(ids_to_fetch)

    print("\nBuilding rows...")
    rows: list[dict] = []
    for order in orders:
        rows.extend(extract_order_rows(order, items_cache))

    df = pd.DataFrame(rows)
    df["purchase_date"] = pd.to_datetime(df["purchase_date"], errors="coerce", utc=True)

    output = "meli_purchase_history.csv"
    df.to_csv(output, index=False, encoding="utf-8")

    print(f"\nExported {len(df)} rows → {output}")
    print(df[["order_id", "purchase_date", "item_title", "order_total_amount"]].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests — verify they pass**

```bash
pytest tests/ -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: row extraction and main() CSV export"
```

---

### Task 10: SETUP.md and final wire-up

**Files:**
- Create: `SETUP.md`

- [ ] **Step 1: Create `SETUP.md`**

````markdown
# Mercado Libre Purchase History — Setup Guide

## Prerequisites

- Python 3.11+
- pip
- A Mercado Libre Mexico account

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Step 1: Run auth.py

```bash
python auth.py
```

What happens:
1. A Chromium browser window opens to the ML Developer Portal.
2. Log in with your ML account. Complete 2FA if prompted.
3. Press ENTER in the terminal when fully logged in.
4. The script attempts to automate app creation. If the portal UI has changed, it will prompt you to create the app manually with these settings:
   - **Name:** anything (e.g. "My Purchase History")
   - **Redirect URI:** `http://localhost:8080`
   - **Scopes:** `read`, `offline_access`
5. Press ENTER once the app is created and visible on screen.
6. The script captures your APP_ID and SECRET_KEY (or prompts you to paste them if auto-capture fails).
7. The OAuth authorization page opens. Click **Authorize**.
8. The script captures the auth code automatically and exchanges it for tokens.

Output files written:
- `credentials.json` — APP_ID + SECRET_KEY
- `tokens.json` — access_token + refresh_token (valid ~6h)

## Step 2: Run extract.py

```bash
python extract.py
```

What happens:
1. Reads `credentials.json` and `tokens.json`.
2. Fetches your user ID from `/users/me`.
3. Paginates all buyer orders (50 per page).
4. Batch-fetches item details for any orders missing product titles.
5. Exports `meli_purchase_history.csv`.

Output: `meli_purchase_history.csv` with columns:
`order_id`, `purchase_date`, `status`, `item_title`, `item_category`,
`item_quantity`, `item_unit_price`, `order_total_amount`, `currency`

## Troubleshooting

| Problem | Solution |
|---|---|
| `Port 8080 already in use` | Run: `lsof -ti:8080 \| xargs kill` |
| `401 Unauthorized` during extract | Re-run `auth.py` — token may be fully expired |
| `403 Forbidden` on orders search | Ensure app scopes include `read` and `offline_access` |
| App creation form not found | Create the app manually on [developers.mercadolibre.com.mx](https://developers.mercadolibre.com.mx/en_us/application-manager), then paste credentials when prompted |
| Empty CSV | Your account may have no purchase history, or the buyer ID wasn't returned correctly |
| `RuntimeError: Failed after 3 retries` | Network connectivity issue — check your connection and re-run `extract.py` |
| Many rows show `item_title = Unknown` | Those items were deleted or delisted from Mercado Libre; titles are no longer available |

## Re-running export without re-authenticating

As long as `tokens.json` is less than 6 hours old, you can re-run `extract.py` without re-running `auth.py`.
````

- [ ] **Step 2: Run full test suite one final time**

```bash
pytest tests/ -v
```
Expected: all pass

- [ ] **Step 3: Final commit**

```bash
git add SETUP.md
git commit -m "docs: add setup guide"
```
