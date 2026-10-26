"""Downloads one product image per ASIN in data/purchases.db into data/images/<ASIN>.jpg.

Resumable: skips ASINs that already have an image or are listed in images/missing.txt.
Tries the product page's main image first, then Amazon's ASIN image URL.
Usage: python3 -I fetch_images.py
"""
import random
import re
import sqlite3
import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data"
IMAGES = ROOT / "images"
MISSING = IMAGES / "missing.txt"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
HIRES = re.compile(r'"hiRes":"(https://m\.media-amazon\.com/images/I/[^"._]+)\.')
# Amazon throttles by IP after roughly a hundred quick requests and lifts it within the hour.
CAPTCHA_WAIT = 300
MAX_CAPTCHAS = 24  # consecutive, i.e. two hours of waiting
LARGE = re.compile(r'"large":"(https://m\.media-amazon\.com/images/I/[^"._]+)\.')


def get(url):
    # Amazon serves a captcha to Python's HTTP client but not to curl.
    cmd = ["curl", "-sfL", "--compressed", "--max-time", "30", "-A", UA,
           "-H", "Accept-Language: es-MX,es;q=0.9,en;q=0.8", url]
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def page_image(site, asin):
    html = get(f"https://www.{site}/dp/{asin}").decode("utf-8", "replace")
    if len(html) < 50000:  # real product pages are 300 KB+; small ones are captcha or block pages
        raise RuntimeError("captcha")
    match = HIRES.search(html) or LARGE.search(html)
    return match and match.group(1) + "._AC_SL500_.jpg"


def fetch(site, asin):
    try:
        url = page_image(site, asin)
    except RuntimeError:
        raise
    except Exception:
        url = None
    for candidate in filter(None, [url, f"https://m.media-amazon.com/images/P/{asin}.01._SL500_.jpg"]):
        try:
            data = get(candidate)
        except Exception:
            continue
        if len(data) > 1000:  # Amazon answers unknown ASINs with a 43-byte blank gif
            return data
    return None


def main():
    IMAGES.mkdir(parents=True, exist_ok=True)
    missing = set(MISSING.read_text().split()) if MISSING.exists() else set()
    db = sqlite3.connect(ROOT / "purchases.db")
    rows = db.execute("select asin, lower(max(site)) from purchases where asin != '' group by asin order by max(date) desc").fetchall()
    todo = [(a, s) for a, s in rows if not (IMAGES / f"{a}.jpg").exists() and a not in missing]
    print(f"{len(rows)} products, {len(todo)} to fetch", flush=True)

    captchas = 0
    for i, (asin, site) in enumerate(todo, 1):
        while True:
            try:
                data = fetch(site, asin)
                break
            except RuntimeError:
                captchas += 1
                if captchas > MAX_CAPTCHAS:
                    sys.exit("Amazon kept answering with captchas; run again later to resume.")
                print(f"[{i}/{len(todo)}] {asin} captcha, waiting {CAPTCHA_WAIT // 60} min", flush=True)
                time.sleep(CAPTCHA_WAIT)
        if data:
            (IMAGES / f"{asin}.jpg").write_bytes(data)
        else:
            with MISSING.open("a") as f:
                f.write(asin + "\n")
        print(f"[{i}/{len(todo)}] {asin} {'ok' if data else 'missing'}", flush=True)
        captchas = 0
        time.sleep(random.uniform(5, 9))  # slow enough that Amazon doesn't throttle the IP


if __name__ == "__main__":
    main()
