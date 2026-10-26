#!/usr/bin/env bash
# Rebuilds data/purchases.db from the newest Amazon "Your Orders" exports, unzipped under
# data/amazon/<YYYY-MM-DD>/<site>/.
# Usage: ./build.sh            (rebuild the DB)
#        ./build.sh serve      (rebuild, then open the search UI on http://127.0.0.1:8001)
set -euo pipefail
cd "$(dirname "$0")/../.."

db=data/purchases.db
latest=$(ls -d data/amazon/*/ 2>/dev/null | sort | tail -1)
[ -n "$latest" ] || { echo "no export in data/amazon/<date>/" >&2; exit 1; }
rm -f "$db"
su() { uvx sqlite-utils "$@"; }

shopt -s nullglob
for dir in "$latest"*/; do
  orders="$dir/Your Amazon Orders/Order History.csv"
  digital="$dir/Your Amazon Orders/Digital Content Orders.csv"
  refunds="$dir/Your Returns & Refunds/Refund Details.csv"
  [ -f "$orders" ] && su insert "$db" orders "$orders" --csv
  [ -f "$digital" ] && su insert "$db" digital_orders "$digital" --csv
  [ -f "$refunds" ] && su insert "$db" refunds "$refunds" --csv
done

su enable-fts "$db" orders "Product Name" Department --create-triggers
if su tables "$db" | grep -q digital_orders; then
  su enable-fts "$db" digital_orders "Product Name" --create-triggers
fi

su create-view "$db" purchases "
  select date(\"Order Date\") as date, Website as site, \"Product Name\" as product,
         Department as department, cast(\"Original Quantity\" as integer) as qty, cast(replace(\"Unit Price\", ',', '') as real) as unit_price,
         cast(replace(\"Total Amount\", ',', '') as real) as total, Currency as currency, \"Order Status\" as status,
         ASIN as asin, 'https://' || lower(Website) || '/dp/' || ASIN as url, \"Order ID\" as order_id
  from orders order by \"Order Date\" desc"

echo "Built $db: $(su query "$db" 'select count(*) as n from orders' --csv | tail -1) physical items"

if [ "${1:-}" = serve ]; then
  uvx datasette "$db" --port 8001 --open \
    --setting default_page_size 200 --setting sql_time_limit_ms 5000
fi
