#!/usr/bin/env bash
# Estimate time spent on twitter/x, linkedin and youtube in Chrome over the last N days
# (default 1 = last 24 hours). Prints "site|visits|estimated hours".
#
# How the estimate works: Chrome's history records how long each page stayed open, which
# includes background tabs, so it overcounts. macOS Screen Time data (knowledgeC.db) knows how
# long Chrome itself was in the foreground. Each site gets its share of the open time,
# applied to Chrome's foreground hours. Rough, but consistent day to day, which is what a
# trend needs. Phone usage is not included.
set -euo pipefail

days="${1:-1}"
chrome=~/"Library/Application Support/Google/Chrome/Default/History"
knowledge=~/"Library/Application Support/Knowledge/knowledgeC.db"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cp "$chrome" "$tmp/history.db"   # Chrome locks the live file

foreground=$(sqlite3 -readonly "file:$knowledge?mode=ro" "
  select coalesce(sum(ZENDDATE - ZSTARTDATE), 0) / 3600.0 from ZOBJECT
  where ZSTREAMNAME = '/app/usage' and ZVALUESTRING = 'com.google.Chrome'
    and ZSTARTDATE > strftime('%s', 'now', '-$days days') - 978307200;")

sqlite3 "$tmp/history.db" "
  with v as (
    select u.url, vi.visit_duration as d from visits vi join urls u on u.id = vi.url
    where vi.visit_time > (strftime('%s', 'now', '-$days days') + 11644473600) * 1000000
  ),
  k as (
    select case
      when url like '%://x.com%' or url like '%://%.x.com%' or url like '%twitter.com%' then 'twitter'
      when url like '%linkedin.com%' then 'linkedin'
      when url like '%youtube.com%' then 'youtube'
      else 'other' end as site, d from v
  ),
  total as (select max(sum(d), 1) as t from k)
  select site, count(*), round(sum(d) * 1.0 / (select t from total) * $foreground, 1)
  from k where site != 'other' group by site
  union all
  select 'chrome-foreground', '', round($foreground, 1);"
