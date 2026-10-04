#!/bin/bash
# Create (or refresh) a Gutenprint queue for the iX6820 that routes through the tone-curve filter.
#   sudo ./add-queue.sh <queue> "<description>" <MediaType> <Density> <Gamma> <Black> [InkLimit]
# Example (plain paper):
#   sudo ./add-queue.sh iX6820-Plain "iX6820 plain" Plain 600 1800 700
# The curve used is curves/<queue>.json if present, else curves/<MediaType>.json, else none.
# Override the USB URI with URI=usb://... if auto-detection picks the wrong device.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo" >&2; exit 1; }
[ $# -ge 6 ] || { sed -n '2,9p' "$0"; exit 2; }
Q=$1; DESC=$2; MT=$3; DENS=$4; GAM=$5; BLK=$6; LIM=${7:-None}
URI=${URI:-$(lpinfo -v 2>/dev/null | awk '/usb:\/\/Canon\/iX68/{print $2; exit}')}
[ -n "$URI" ] || { echo "No iX68xx found on USB. Plug it in, or set URI=usb://..." >&2; exit 1; }
MODEL=$(lpinfo -m 2>/dev/null | awk '/gutenprint.*bjc-iX6800-series/{print $1; exit}')
[ -n "$MODEL" ] || { echo "Gutenprint iX6800 driver not found (install printer-driver-gutenprint)." >&2; exit 1; }
lpadmin -p "$Q" -E -v "$URI" -m "$MODEL" -D "$DESC" -o printer-is-shared=false
PPD=$(mktemp); trap 'rm -f "$PPD"' EXIT
curl -fsS "http://localhost:631/printers/$Q.ppd" \
  | sed 's|^\(\*cupsFilter:.*\) rastertogutenprint\.[0-9.]*"|\1 rastertogutenprint-curve"|' > "$PPD"
grep -q 'rastertogutenprint-curve' "$PPD" || { echo "Could not patch the PPD filter line." >&2; exit 1; }
lpadmin -p "$Q" -P "$PPD"
lpadmin -p "$Q" -o StpDensity-default="$DENS" -o StpGamma-default="$GAM" -o StpBlackDensity-default="$BLK" \
       -o StpInkLimit-default="$LIM" -o StpImageType-default=Photo -o MediaType-default="$MT" -o PageSize-default=Letter
echo "Queue $Q ready on $URI (MediaType=$MT density=$DENS gamma=$GAM black=$BLK inklimit=$LIM)"
