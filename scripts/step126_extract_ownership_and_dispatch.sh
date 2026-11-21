#!/usr/bin/env bash
# Step 126: read-only inspection of HTTP retain/release and queue wake paths.
set -euo pipefail

if [[ -n "\${AK3918_ROOT:-}" ]]; then
    ROOT="$AK3918_ROOT"
elif [[ -f "$HOME/AK3918_Diagnostics/stock_analysis/sdDongle" ]]; then
    ROOT="$HOME/AK3918_Diagnostics"
else
    ROOT="$HOME/AK3918/01_Development/AK3918_Diagnostics/ak3918-sigsegv-fix"
fi
STOCK="$ROOT/stock_analysis/sdDongle"
REPORT="\${1:-$HOME/Desktop/AK3918_step126_ownership_and_dispatch.txt}"
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

echo "PASS: Verified stock ELF; extracting ownership/dispatch control flow"
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
# Resolve the two adjacent CF reference helpers called by stock send.
dump "CF REFERENCE HELPERS AND WRAPPERS" 0x82c30 0x82cc0
dump "CF RETAIN AND RELEASE IMPLEMENTATIONS" 0x85b20 0x85d30

# Track the queue's node ownership and optional indirect wake callback.
dump "HTTP QUEUE PUSH / WAKE" 0xa18d8 0xa1b24
dump "HTTP QUEUE ADJACENT PROCESSOR" 0xa1b74 0xa1e30
dump "HTTP QUEUE INITIALIZATION / WAKE FUNCTION" 0xa0454 0xa0550
dump "HTTP RESPONSE COMPLETION HELPER" 0xa1338 0xa1490

# Examine the stock session's own teardown hooks and cleanup.
dump "SESSION FINALIZER CALLBACK CONTINUATION" 0x66a40 0x66c50
dump "SESSION CALLBACK FOLLOW-UP" 0x7c060 0x7c190
AK3918_READONLY

if [[ ! -s "$TEMP_REPORT" ]] ||
   ! grep -Eq '^[[:space:]]*0*82c74:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*82c78:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*a1900:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*a1b74:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*66a94:' "$TEMP_REPORT"; then
    echo "FAIL: Incomplete Step 126 disassembly. Original report preserved." >&2
    exit 1
fi
mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 126 report created at $REPORT"
ls -lh "$REPORT"
echo "No firmware was modified, packaged, installed or flashed."
