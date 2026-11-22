#!/usr/bin/env bash
# Step 131: prove exact verified-stock HTTPClientSendMessage error paths.
# Only read the stock ELF. Never rebuild, modify, package, install or flash.
set -euo pipefail

if [[ -n "${AK3918_ROOT:-}" ]]; then
    ROOT="$AK3918_ROOT"
elif [[ -f "$HOME/AK3918_Diagnostics/stock_analysis/sdDongle" ]]; then
    ROOT="$HOME/AK3918_Diagnostics"
else
    ROOT="$HOME/AK3918/01_Development/AK3918_Diagnostics/ak3918-sigsegv-fix"
fi
STOCK="$ROOT/stock_analysis/sdDongle"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="${1:-$HOME/Desktop/AK3918_step131_http_return.txt}"
EXPECTED=b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1

if [[ ! -f "$STOCK" ]]; then
    echo "FAIL: stock ELF missing: $STOCK" >&2
    exit 1
fi
if command -v shasum >/dev/null 2>&1; then
    ACTUAL="$(shasum -a 256 "$STOCK" | awk '{print $1}')"
else
    ACTUAL="$(sha256sum "$STOCK" | awk '{print $1}')"
fi
if [[ "$EXPECTED" != "$ACTUAL" ]]; then
    echo "FAIL: stock ELF checksum mismatch; refusing analysis" >&2
    exit 1
fi
command -v docker >/dev/null 2>&1 || {
    echo "FAIL: Docker unavailable" >&2
    exit 1
}
mkdir -p "$(dirname "$REPORT")"
TEMP_REPORT="$(mktemp "$REPORT.tmp.XXXXXX")"
trap 'rm -f "$TEMP_REPORT"' EXIT

docker run --rm --platform linux/arm64 -i \
  -v "$ROOT:/repo:ro" \
  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
  --entrypoint /bin/bash ak3918-buildroot:latest -s > "$TEMP_REPORT" <<'ARM_READ_ONLY'
set -euo pipefail
OBJDUMP=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi-objdump
STOCK=/repo/stock_analysis/sdDongle
test -x "$OBJDUMP"
test -r "$STOCK"
echo "=== Verified original stock HTTPClientSendMessage 0xA6974..0xA6A7C ==="
"$OBJDUMP" -d --start-address=0xa6974 --stop-address=0xa6a80 "$STOCK"
ARM_READ_ONLY

python3 "$HERE/scripts/step131_verify_http_return.py" "$TEMP_REPORT"
mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 131 verified-stock HTTP return report created at $REPORT"
echo "No firmware was modified, packaged, installed or flashed."
