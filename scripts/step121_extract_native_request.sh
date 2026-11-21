#!/usr/bin/env bash
# Step 121: read-only native request lifecycle disassembly from verified stock ELF.
set -euo pipefail

ROOT="${AK3918_ROOT:-$HOME/AK3918/01_Development/AK3918_Diagnostics/ak3918-sigsegv-fix}"
STOCK="$ROOT/stock_analysis/sdDongle"
REPORT="${1:-$HOME/Desktop/AK3918_step121_native_request_lifecycle.txt}"
EXPECTED="b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1"

if [[ ! -f "$STOCK" ]]; then
    echo "FAIL: Original stock sdDongle not found at $STOCK" >&2
    exit 1
fi
if command -v shasum >/dev/null 2>&1; then
    ACTUAL="$(shasum -a 256 "$STOCK" | awk '{print $1}')"
else
    ACTUAL="$(sha256sum "$STOCK" | awk '{print $1}')"
fi
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "FAIL: Stock firmware SHA-256 mismatch" >&2
    exit 1
fi
command -v docker >/dev/null 2>&1 || { echo "FAIL: Docker unavailable" >&2; exit 1; }
mkdir -p "$(dirname "$REPORT")"

echo "PASS: Verified stock ELF; extracting read-only control flow"
docker run --rm --platform linux/arm64 \
  -v "$ROOT:/repo:ro" \
  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
  --entrypoint /bin/bash \
  ak3918-buildroot:latest -c '
set -euo pipefail
OBJDUMP=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi-objdump
STOCK=/repo/stock_analysis/sdDongle
test -x "$OBJDUMP"
test -r "$STOCK"
dump() {
    printf "\n===== %s =====\n" "$1"
    "$OBJDUMP" -d --start-address="$2" --stop-address="$3" "$STOCK"
}
dump "OUTGOING REQUEST INITIALIZATION" 0x2f6b8 0x2f850
dump "STREAM 111 INSERTION / SERIALIZE / SEND CALLS" 0x2fa90 0x2fbc0
dump "NATIVE SEND FAILURE AND RELEASE PATHS" 0x2fbe8 0x2fe40
dump "PLIST SERIALIZATION FUNCTION" 0x8d0a0 0x8d3c0
dump "HTTP MESSAGE CONSTRUCTION" 0xa6d08 0xa6f40
dump "HTTP SEND FUNCTION" 0xa6974 0xa6d08
' > "$REPORT"

echo "PASS: Step 121 report created at $REPORT"
ls -lh "$REPORT"
echo "No firmware was modified, packaged, or installed."
