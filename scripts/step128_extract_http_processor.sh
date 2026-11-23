#!/usr/bin/env bash
# Step 128: read-only stock HTTP client processor and message release audit.
set -euo pipefail

if [[ -n "${AK3918_ROOT:-}" ]]; then
    ROOT="$AK3918_ROOT"
elif [[ -f "$HOME/AK3918_Diagnostics/stock_analysis/sdDongle" ]]; then
    ROOT="$HOME/AK3918_Diagnostics"
else
    ROOT="$HOME/AK3918/01_Development/AK3918_Diagnostics/ak3918-sigsegv-fix"
fi
STOCK="$ROOT/stock_analysis/sdDongle"
REPORT="${1:-$HOME/Desktop/AK3918_step128_http_processor.txt}"
EXPECTED="b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1"

if [[ ! -f "$STOCK" ]]; then
    echo "FAIL: Verified stock executable missing: $STOCK" >&2
    exit 1
fi
if command -v shasum >/dev/null 2>&1; then
    ACTUAL="$(shasum -a 256 "$STOCK" | awk '{print $1}')"
else
    ACTUAL="$(sha256sum "$STOCK" | awk '{print $1}')"
fi
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "FAIL: Stock sdDongle hash mismatch; refusing disassembly" >&2
    exit 1
fi
command -v docker >/dev/null 2>&1 || {
    echo "FAIL: Docker not available" >&2
    exit 1
}

mkdir -p "$(dirname "$REPORT")"
TEMP_REPORT="$(mktemp "$REPORT.tmp.XXXXXX")"
trap 'rm -f "$TEMP_REPORT"' EXIT

echo "PASS: Verified stock ELF; extracting HTTP processor and release control flow"
docker run --rm --platform linux/arm64 -i \
  -v "$ROOT:/repo:ro" \
  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
  --entrypoint /bin/bash \
  ak3918-buildroot:latest -s > "$TEMP_REPORT" <<'AK3918_READONLY'
set -euo pipefail
OBJDUMP=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi-objdump
STOCK=/repo/stock_analysis/sdDongle
test -x "$OBJDUMP"
test -r "$STOCK"

dump() {
    printf "\n===== %s =====\n" "$1"
    "$OBJDUMP" -d --start-address="$2" --stop-address="$3" "$STOCK"
}
# Step 127 established that 0xa6040 is an enqueue-dispatched callback
# which moves a message into its HTTP client's queue, calls 0xa53fc, then
# releases the HTTP client. That does not yet prove message release.
# Inspect the full native HTTP client state-machine around 0xa53fc.
dump "HTTP CLIENT PROCESSOR ENTRY" 0xa52c0 0xa56c0
dump "HTTP CLIENT PROCESSOR MIDDLE" 0xa56c0 0xa5ac0
dump "HTTP CLIENT PROCESSOR EXIT AND ERROR PATHS" 0xa5ac0 0xa6040
dump "QUEUED CALLBACK AND CLIENT RELEASE" 0xa6040 0xa6074
dump "HTTP CLIENT OR MESSAGE REFERENCE HANDOFF" 0xa6974 0xa6a80
dump "STOCK SCREEN RESPONSE CALLBACK AND DATA PORT HANDOFF" 0x2ec7c 0x2ee90
AK3918_READONLY

if [[ ! -s "$TEMP_REPORT" ]] ||
   ! grep -Eq '^[[:space:]]*0*a53fc:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*a6040:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*a6070:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*a6a54:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*2ee74:' "$TEMP_REPORT"; then
    echo "FAIL: Incomplete Step 128 disassembly. Original report preserved." >&2
    exit 1
fi
mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 128 report created at $REPORT"
ls -lh "$REPORT"
echo "No firmware was modified, packaged, installed or flashed."
