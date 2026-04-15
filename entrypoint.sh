#!/bin/sh
set -e

PUID="${PUID:-99}"
PGID="${PGID:-100}"

groupadd -o -g "$PGID" siphon 2>/dev/null || true
useradd -o -u "$PUID" -g siphon -s /bin/sh -M siphon 2>/dev/null || true

umask "${UMASK:-022}"

chown siphon:siphon /app/.data /app/downloads

exec gosu siphon "$@"
