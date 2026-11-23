#!/usr/bin/env bash
# Step 127: read-only native HTTP queue callback and drain audit.
set -euo pipefail

if [[ -n "${AK3918_ROOT:-}" ]]; then
    ROOT="$AK3918_ROOT"
elif [[ -f "$HOME/AK3918_Diagnostics/stock_analysis/sdDongle" ]]; then
    ROOT="$HOME/AK3918_Diagnostics"
else
    ROOT="$HOME/AK3918/01_Development/AK3918_Diagnostics/ak3918-sigsegv-fix"
fi
STOCK="$ROOT/stock_analysis/sdDongle"
REPORT="${1:-$HOME/Desktop/AK3918_step127_queue_completion.txt}"
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

echo "PASS: Verified stock ELF; extracting queue completion control flow"
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
# Resolve the callback address passed as argument r2 to the native queue
# from stock HTTP send at a6a58..a6a6c. At a6a60, PC-relative addition is
# (0xa6a60 + 8) + (signed32)0xfffff5d8 = 0xa6040.
dump "HTTP QUEUED COMPLETION CALLBACK AND NEIGHBOURS" 0xa5e80 0xa6320

# Identify actual queue-drain/dequeue operations, rather than the adjacent
# socket helper (a1b74), which is a queue PRODUCER.
dump "HTTP QUEUE DRAIN CANDIDATES BEFORE ENQUEUE" 0xa14a0 0xa18d8
dump "HTTP QUEUE DISPATCH AND MUTEX" 0xa1900 0xa1b24
dump "HTTP RESPONSE COMPLETION AND WAKE" 0xa12c0 0xa13b8

# Check native HTTP client/message cleanup context, and session finalizer.
dump "HTTP MESSAGE DESTROY / CALLBACK NEIGHBOURS" 0xa63d0 0xa6974
dump "RECEIVER FINALIZER CLEANUP" 0x66a80 0x66c1c
AK3918_READONLY

if [[ ! -s "$TEMP_REPORT" ]] ||
   ! grep -Eq '^[[:space:]]*0*a6040:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*a1900:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*a1338:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*66a94:' "$TEMP_REPORT"; then
    echo "FAIL: Incomplete Step 127 disassembly. Original report preserved." >&2
    exit 1
fi
mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 127 report created at $REPORT"
ls -lh "$REPORT"
echo "No firmware was modified, packaged, installed or flashed."
