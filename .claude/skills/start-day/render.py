"""Render the start-day page: python3 -I render.py <day.json> <out.html>

Validates the day's JSON and injects it into template.html next to this script.
"""
import json
import pathlib
import sys

REQUIRED = ["date", "dateLabel", "greeting", "nextAction", "quotes", "habits", "goals"]

data_path, out_path = map(pathlib.Path, sys.argv[1:3])
data = json.loads(data_path.read_text())

missing = [k for k in REQUIRED if not data.get(k)]
if missing:
    sys.exit(f"missing or empty fields: {', '.join(missing)}")
for q in data["quotes"]:
    if not q.get("text") or not q.get("author"):
        sys.exit(f"every quote needs text and author: {q}")
if len(data["goals"]) > 3:
    sys.exit("at most 3 goals; move the rest to another day")

template = (pathlib.Path(__file__).parent / "template.html").read_text()
# "</" must not appear raw inside a <script> block.
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
out_path.write_text(template.replace("__DAY_DATA__", payload))
print(out_path)
