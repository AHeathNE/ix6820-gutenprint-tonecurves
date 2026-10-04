#!/bin/bash
# Install the tone-curve filter and the curve files. Does not touch any print queue.
#   sudo ./install.sh
set -euo pipefail
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo "Run with sudo" >&2; exit 1; }
SERVERBIN=$(cups-config --serverbin 2>/dev/null || echo /usr/lib/cups)
DATADIR=$(cups-config --datadir 2>/dev/null || echo /usr/share/cups)
install -m 755 -o root -g root filter/rastertogutenprint-curve "$SERVERBIN/filter/rastertogutenprint-curve"
install -m 755 -o root -g root filter/rastertogutenprint-curve "$SERVERBIN/filter/rastertopwg-curve"   # for driverless queues
install -d -m 755 "$DATADIR/tone-curves"
for c in curves/*.json; do install -m 644 -o root -g root "$c" "$DATADIR/tone-curves/$(basename "$c")"; done
echo "Filter  -> $SERVERBIN/filter/rastertogutenprint-curve"
echo "Curves  -> $DATADIR/tone-curves/: $(ls "$DATADIR/tone-curves" | tr '\n' ' ')"
echo "Next: sudo ./add-queue.sh <queue> \"<description>\" <MediaType> <Density> <Gamma> <Black>"
