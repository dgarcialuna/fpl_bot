#!/usr/bin/env bash
# Consistent copy of the live SQLite database, keeping the last 14 days.
set -euo pipefail

DB="${FPL_BOT_DB:-/var/lib/fpl-bot/fpl_bot.db}"
DEST="$(dirname "$DB")/backups"
mkdir -p "$DEST"

STAMP="$(date -u +%Y%m%d)"
python3 - "$DB" "$DEST/fpl_bot-$STAMP.db" <<'PY'
import sqlite3
import sys

src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
dst.close()
src.close()
PY

# Remove backups older than 14 days.
find "$DEST" -name 'fpl_bot-*.db' -mtime +14 -delete
