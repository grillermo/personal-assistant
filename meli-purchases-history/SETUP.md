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

## Quick Start

```bash
python import_orders.py
```

This runs the full workflow in one command:
1. Checks if `tokens.json` exists and is fresh (< 6h old).
2. If missing or stale, runs auth (OAuth flow below).
3. Fetches all orders and exports `meli_purchase_history.csv`.

Output: `meli_purchase_history.csv` with columns:
`order_id`, `purchase_date`, `status`, `item_title`, `item_category`,
`item_quantity`, `item_unit_price`, `order_total_amount`, `currency`

## Manual Workflow (optional reference)

### Step 1: auth.py

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

### Step 2: extract.py

```bash
python extract.py
```

What happens:
1. Reads `credentials.json` and `tokens.json`.
2. Fetches your user ID from `/users/me`.
3. Paginates all buyer orders (50 per page).
4. Batch-fetches item details for any orders missing product titles.
5. Exports `meli_purchase_history.csv`.

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

## Re-running export

`import_orders.py` handles token expiration automatically:
- If `tokens.json` is fresh (< 6h old), it skips auth and goes straight to extract.
- If missing or stale, it re-authenticates first.

Just run `python import_orders.py` each time.
