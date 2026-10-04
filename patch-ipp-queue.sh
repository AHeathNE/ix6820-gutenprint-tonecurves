#!/bin/bash
# Route an existing driverless (IPP Everywhere) queue through the tone-curve filter.
#   sudo ./patch-ipp-queue.sh <queue> [default-quality]
# e.g. sudo ./patch-ipp-queue.sh TC-20M High
# Curves: curves/<queue>.<quality>.json, then <queue>.json, then <MediaType>.json; none = pass-through.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo" >&2; exit 1; }
cd "$(dirname "$0")"
Q=${1:?usage: sudo ./patch-ipp-queue.sh <queue> [default-quality]}; QUAL=${2:-}
SERVERBIN=$(cups-config --serverbin 2>/dev/null || echo /usr/lib/cups)
DATADIR=$(cups-config --datadir 2>/dev/null || echo /usr/share/cups)
install -m 755 -o root -g root filter/rastertogutenprint-curve "$SERVERBIN/filter/rastertogutenprint-curve"
install -m 755 -o root -g root filter/rastertogutenprint-curve "$SERVERBIN/filter/rastertopwg-curve"
install -d -m 755 "$DATADIR/tone-curves"
for c in curves/*.json; do install -m 644 -o root -g root "$c" "$DATADIR/tone-curves/$(basename "$c")"; done
PPD=$(mktemp); trap 'rm -f "$PPD"' EXIT
curl -fsS "http://localhost:631/printers/$Q.ppd" > "$PPD"
grep -q '^\*cupsFilter2:' "$PPD" || { echo "Queue $Q has no cupsFilter2 lines; is it a driverless queue?" >&2; exit 1; }
if ! grep -q 'rastertopwg-curve' "$PPD"; then
  # 1) drop the JPEG pass-through so JPEGs are rendered by CUPS and get the curve
  # 2) add raster -> URF through our wrapper (cost 0 beats the stock converter)
  awk '
    /^\*cupsFilter2:.*"image\/jpeg image\/jpeg 0 -"/ { next }
    { print }
    /^\*cupsFilter2:/ && !done { print "*cupsFilter2: \"application/vnd.cups-raster image/urf 0 rastertopwg-curve\""; done=1 }
  ' "$PPD" > "$PPD.new" && mv "$PPD.new" "$PPD"
fi
lpadmin -p "$Q" -P "$PPD"
[ -n "$QUAL" ] && lpadmin -p "$Q" -o cupsPrintQuality-default="$QUAL"
echo "Queue $Q now uses the tone-curve filter. Curves: $(ls "$DATADIR/tone-curves" | tr '\n' ' ')"
