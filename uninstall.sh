#!/bin/bash
# Remove the filter and curve files. Queues made by add-queue.sh are left (remove with: lpadmin -x <queue>).
#   sudo ./uninstall.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo" >&2; exit 1; }
SERVERBIN=$(cups-config --serverbin 2>/dev/null || echo /usr/lib/cups)
DATADIR=$(cups-config --datadir 2>/dev/null || echo /usr/share/cups)
rm -f "$SERVERBIN/filter/rastertogutenprint-curve"; rm -rf "$DATADIR/tone-curves"
echo "Removed. Any queue still using the filter will fail until you delete or repoint it (lpadmin -x <queue>)."
