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

    def get(self, url: str, params: dict | None = None, retries: int = 3) -> dict | list:
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
        data = self.get(f"{API_BASE}/users/me")
        assert isinstance(data, dict)
        return data["id"]

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
            assert isinstance(data, dict)
            results = data.get("results", [])
            total = data.get("paging", {}).get("total", 0)
            orders.extend(results)
            offset += len(results)
            print(f"  Progress: {len(orders)}/{total}")

            if not results or offset >= total:
                break
            time.sleep(0.5)

        return orders

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
