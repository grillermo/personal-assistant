# Mercado Libre Purchase History Extractor — Design Spec

**Date:** 2026-06-13  
**Status:** Approved

---

## Goal

Programmatically retrieve and export the complete purchase history from a Mercado Libre Mexico account into a UTF-8 CSV file. Requires browser automation to handle OAuth and (optionally) developer app creation, then pure API calls for data extraction.

---

## File Structure

```
purchases-history/
├── auth.py              # Phase 1: Playwright automation + OAuth
├── extract.py           # Phase 2–4: API extraction + CSV export
├── requirements.txt
├── SETUP.md
├── .gitignore           # excludes credentials.json, tokens.json, *.csv
├── credentials.json     # runtime artifact — APP_ID, SECRET_KEY
└── tokens.json          # runtime artifact — access_token, refresh_token
```

---

## Phase 1: auth.py

### Responsibility
Browser automation via Playwright (non-headless Chromium) to:
1. Walk the user through ML developer portal login (minimal manual steps — only login + 2FA require human input)
2. Automate app creation form if possible; fall back to guided manual step if ML UI is unrecognised
3. Capture APP_ID and SECRET_KEY from the page DOM
4. Run the OAuth authorization code flow and capture the `code` parameter
5. Exchange the code for tokens and persist `credentials.json` + `tokens.json`

### OAuth Capture Mechanism
- Start `http.server.HTTPServer` on `localhost:8080` in a background `threading.Thread`
- Redirect URI registered in the ML app: `http://localhost:8080`
- Required OAuth scopes: `read`, `offline_access`
- Navigate browser to `https://auth.mercadolibre.com.mx/authorization?response_type=code&client_id={APP_ID}&redirect_uri=http://localhost:8080&scope=read%20offline_access`
- User clicks "Authorize" in browser window
- ML redirects browser to `http://localhost:8080/?code=...`
- Background server captures `code`; main thread polls until code appears, then closes browser
- After code is captured: call `server.shutdown()` and `thread.join()` to cleanly stop the server

### Token Exchange
`POST https://api.mercadolibre.com/oauth/token` with:
- `grant_type=authorization_code`
- `client_id`, `client_secret`, `code`, `redirect_uri`

Response persisted to `tokens.json`.

### Outputs
- `credentials.json` — `{ "app_id": "...", "secret_key": "..." }`
- `tokens.json` — full token response including `access_token`, `refresh_token`, `expires_in`

---

## Phase 2–4: extract.py

### MeliClient Class
Thread-safe API client with:
- `access_token` from `tokens.json`, protected by `threading.Lock`
- On load, compute `refresh_at = time.time() + tokens["expires_in"] - 300` (5-minute buffer before actual expiry)
- Background `threading.Thread` that sleeps until `refresh_at`, then calls `POST /oauth/token` with `grant_type=refresh_token`, persists updated tokens, and recomputes next `refresh_at`
- `get(url, params, retries=3)` method with:
  - `401` → immediate token refresh + retry
  - `429` → read `Retry-After` header, sleep, retry
  - Other errors → exponential backoff (2^attempt seconds), raise after `retries` exhausted

### User Identification
`GET https://api.mercadolibre.com/users/me` → extract `id` field → `USER_ID`

### Order Pagination
```
GET /orders/search?buyer={USER_ID}&offset={n}&limit=50
```
Use default sort (date_desc — ML does not reliably support `date_asc` for buyer searches). Loop: increment `offset` by `len(results)` each iteration; stop when `offset >= paging.total` or `results` is empty. Sleep 0.5s between pages to avoid rate limits.

### Item Hydration
1. First pass: collect titles already present in `order_items[].item.title` (ML often includes them; no API call needed)
2. Collect item IDs with missing titles
3. Batch `GET /items?ids=id1,id2,...` (max 20 IDs per call) via `ThreadPoolExecutor(max_workers=5)`
4. Response is `[{code: int, body: {...}}, ...]` — filter for `code == 200` before extracting `body.title` and `body.category_id`; items with non-200 codes (deleted, unlisted) yield "Unknown" for title/category

### CSV Output
`pandas.DataFrame` → `meli_purchase_history.csv` (UTF-8, no BOM)

| Column | Source |
|---|---|
| `order_id` | `order.id` |
| `purchase_date` | `order.date_created` (parsed to datetime) |
| `status` | `order.status` |
| `item_title` | `order_items[].item.title` or hydrated |
| `item_category` | hydrated `body.category_id` |
| `item_quantity` | `order_items[].quantity` |
| `item_unit_price` | `order_items[].unit_price` |
| `order_total_amount` | `order.total_amount` (same value repeated for all rows of a multi-item order) |
| `currency` | `order.currency_id` |

One row per order item (orders with multiple items produce multiple rows sharing the same `order_id` and `order_total_amount`).

---

## requirements.txt

```
playwright>=1.40.0
requests>=2.31.0
pandas>=2.1.0
```

---

## Error Handling Summary

| Scenario | Handling |
|---|---|
| Port 8080 in use | Raise with clear message to free the port |
| ML dev portal UI changed | Fall back to manual: pause + prompt user to copy credentials |
| 401 Unauthorized | Refresh token immediately, retry once |
| 429 Rate Limited | Sleep `Retry-After` seconds, retry |
| Item fetch fails | Log warning, use "Unknown" for title/category |
| Network error | Exponential backoff × 3, then raise |

---

## Security

- `credentials.json` and `tokens.json` excluded via `.gitignore`
- No secrets hardcoded
- Tokens stored locally only

---

## Deliverables

1. `auth.py`
2. `extract.py`
3. `requirements.txt`
4. `SETUP.md` — setup guide covering prerequisites, installation, step-by-step run instructions, troubleshooting
5. `.gitignore`
