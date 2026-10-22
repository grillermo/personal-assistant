#!/usr/bin/env bash
# Print open (not completed) reminders from the macOS Reminders app as
# "list|title|due date|priority|notes". Reads the Reminders SQLite stores
# read-only; much faster than AppleScript, which can hang for minutes.
# Optional argument: a list name to filter on, e.g. bin/reminders.sh General
set -euo pipefail

stores=~/"Library/Group Containers/group.com.apple.reminders/Container_v1/Stores"
filter="${1:-}"

for db in "$stores"/Data-*.sqlite; do
  sqlite3 -readonly "file:$db?mode=ro" "
    select l.ZNAME, r.ZTITLE,
           coalesce(date(r.ZDUEDATE + 978307200, 'unixepoch'), ''),
           r.ZPRIORITY,
           replace(substr(coalesce(r.ZNOTES, ''), 1, 160), char(10), ' ')
    from ZREMCDREMINDER r
    left join ZREMCDBASELIST l on l.Z_PK = r.ZLIST
    where r.ZCOMPLETED = 0 and r.ZMARKEDFORDELETION = 0
      and ('$filter' = '' or l.ZNAME = '$filter')
    order by l.ZNAME, r.ZDUEDATE;" 2>/dev/null || true
done
