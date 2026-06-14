# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Mercado Libre Purchase History Exporter** — Fetches and exports a user's complete purchase history from Mercado Libre (Mexican e-commerce platform) into a CSV file via OAuth2 authentication and REST API.

## Common Commands

### Quick Start
```bash
python import_orders.py
```
Runs the full workflow: authenticates (if needed), fetches all orders, exports `meli_purchase_history.csv`. Handles token expiration automatically.

### Manual Workflow
```bash
python auth.py              # OAuth2 login, saves credentials.json + tokens.json
python extract.py          # Fetch orders and export CSV
```

### Testing
```bash
pytest                      # Run all tests
pytest tests/test_auth.py   # Test auth module only
pytest tests/test_extract.py # Test extract module only
pytest -v                   # Verbose output
```

### Environment Setup
```bash
python -m venv python_env
source python_env/bin/activate
pip install -r requirements.txt
```

## Architecture

### Three-Layer Design

**1. Auth Layer (auth.py)**
- Implements OAuth2 authorization code flow for Mercado Libre
- Spins up local HTTP server on `localhost:{MELI_CALLBACK_PORT}` to catch redirect
- Captures authorization code from ML callback URL
- Exchanges code for access/refresh tokens
- Saves credentials (app_id, secret_key) and tokens to JSON files

**2. API Client Layer (extract.py)**
- `MeliClient` class: thread-safe HTTP client with automatic token refresh
- Background thread refreshes token 5 minutes before expiry
- Automatic retry (3 attempts) with exponential backoff on 5xx errors
- Rate limit handling (429 status, respects `Retry-After` header)
- Detects mid-flight token expiry (401) and refreshes immediately
- Paginates orders with offset loop (50 per page)
- Fetches by yearly date ranges to work around API's 5000-result pagination cap
- Batch-fetches item metadata (20 items per request, 5 workers concurrently)

**3. Orchestration Layer (import_orders.py)**
- Checks if `tokens.json` exists and is fresh (< 6h old)
- If fresh, skips auth and goes straight to extraction
- If missing/stale, triggers auth workflow
- Calls extract module to fetch and export

### Data Flow
```
import_orders.py
├─ [Check token freshness]
├─ auth.py (if needed)
│  └─ OAuth2 → credentials.json, tokens.json
└─ extract.py
   ├─ MeliClient (thread-safe, auto-refresh)
   ├─ Fetch /users/me (user ID)
   ├─ Fetch orders by year
   ├─ Batch-fetch item titles
   └─ CSV export
```

### Key Classes & Functions

**extract.py**
- `MeliClient` — HTTP client with token refresh, retry, rate limiting
  - `get()` — Main request method with retry/refresh logic
  - `get_user_id()` — Fetch authenticated user's ID
  - `get_all_orders(user_id, start_year=2022)` — Paginate all orders by year
  - `hydrate_items(item_ids)` — Batch-fetch missing product titles
  - `_refresh_token()` — Manual token refresh (called by daemon thread)
  - `_start_refresh_thread()` — Spawn daemon to auto-refresh before expiry

- `collect_item_ids(orders)` → tuple[list[str], set[str]] — Extract all product IDs from orders
- `extract_order_rows(order, items_cache)` → list[dict] — Flatten order + items into exportable rows

**auth.py**
- `run_auth()` → tuple[app_id, secret_key, code] — Browser-based OAuth flow
- `exchange_code_for_tokens()` — Token exchange
- `parse_oauth_code(path)` → str — Extract code from OAuth redirect
- `start_oauth_server()`, `stop_oauth_server()` — Manage local HTTP server

## Configuration

**Environment Variables (.env)**
- `MELI_CLIENT_ID` — App ID from ML Developer Portal
- `MELI_CLIENT_SECRET` — App secret
- `MELI_REDIRECT_URI` — Callback URL (e.g., public tunnel → localhost:8080)
- `MELI_CALLBACK_PORT` — Local port for OAuth callback (default: 8080)

**Saved Files**
- `credentials.json` — {app_id, secret_key} — persist across runs
- `tokens.json` — {access_token, refresh_token, expires_in} — auto-refreshed by background thread
- `.env` — Local credentials (not in git)
- `meli_purchase_history.csv` — Output (not in git)

## Testing Notes

- Uses `pytest` with `unittest.mock` for HTTP mocking
- Tests are isolated: fixture function `_write_fixtures()` writes minimal credentials/tokens to tmp_path
- Mock `requests.get`/`post` to avoid live API calls
- Key test patterns:
  - OAuth code parsing edge cases
  - Token refresh on 401
  - Rate limit retry on 429
  - Token age calculation (5-min safety buffer)

## Common Issues & Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| `Port 8080 already in use` | Another process owns port | `lsof -ti:8080 \| xargs kill` |
| `401 Unauthorized` during extract | Token expired | Re-run `python auth.py` |
| `app_id = None` in auth flow | .env not loaded | `source python_env/bin/activate` or check `.env` exists |
| `Failed after 3 retries` | Network error or API down | Retry `python import_orders.py` |
| Empty CSV output | No orders on account, or buyer ID lookup failed | Check user ID fetched correctly in logs |
| `Item titles = Unknown` | Product delisted from ML | Item metadata no longer available — expected |

## Git & Commits

- Branch-based workflow with conventional commits
- Test before committing (`pytest`)
- Avoid committing `credentials.json`, `tokens.json`, `.csv` files (in `.gitignore`)

## Development Tip

When debugging API interactions, temporarily add logging in `MeliClient.get()`:
```python
print(f"[DEBUG] GET {url}, params={params}")
print(f"[DEBUG] Response: {resp.status_code}")
```

Then re-run `python import_orders.py` to see request/response details.
