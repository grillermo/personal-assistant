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
