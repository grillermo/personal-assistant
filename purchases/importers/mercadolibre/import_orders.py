import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TOKENS_PATH = "tokens.json"
CREDS_PATH = "credentials.json"


def tokens_valid() -> bool:
    p = Path(TOKENS_PATH)
    if not p.exists():
        return False
    try:
        tokens = json.loads(p.read_text())
        if not tokens.get("access_token") or not tokens.get("refresh_token"):
            return False
        expires_in = tokens.get("expires_in", 21600)
        age = time.time() - p.stat().st_mtime
        return age < expires_in - 300  # 5-min safety buffer
    except Exception:
        return False


def run_auth_and_save() -> None:
    from auth import run_auth, exchange_code_for_tokens, save_credentials, save_tokens

    print("=== Auth required ===")
    app_id, secret_key, code = run_auth()
    redirect_uri = os.getenv("MELI_REDIRECT_URI")
    if not redirect_uri:
        raise ValueError("Missing MELI_REDIRECT_URI in .env")
    tokens = exchange_code_for_tokens(app_id, secret_key, code, redirect_uri)
    save_credentials(app_id, secret_key, CREDS_PATH)
    save_tokens(tokens, TOKENS_PATH)
    expires_h = tokens.get("expires_in", 21600) // 3600
    print(f"Auth done. Token valid ~{expires_h}h.\n")


def run_extract() -> None:
    from extract import MeliClient, collect_item_ids, extract_order_rows
    import pandas as pd

    print("=== Mercado Libre Purchase History Extractor ===\n")
    client = MeliClient(tokens_path=TOKENS_PATH, creds_path=CREDS_PATH)

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


def main() -> None:
    if tokens_valid():
        print("Tokens found, skipping auth.\n")
    else:
        run_auth_and_save()

    run_extract()


if __name__ == "__main__":
    main()
