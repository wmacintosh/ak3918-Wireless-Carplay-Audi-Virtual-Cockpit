#!/usr/bin/env bash
# Step 132: read-only native queue-destructor and HTTP cancellation audit.
# Only read the SHA-256-verified stock ELF. Never rebuild, modify, package, install or flash.
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
REPORT="${1:-$HOME/Desktop/AK3918_step132_queue_cancellation.txt}"
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
dump() {
    printf '\n===== %s =====\n' "$1"
    "$OBJDUMP" -d --start-address="$2" --stop-address="$3" "$STOCK"
}

# The original verified stock ELF has a queue destructor which checks
# queue+0x30. A nonempty queue MUST NOT be assumed to have dispatched callbacks.
dump "DISPATCH QUEUE DESTRUCTOR pending node handling" 0xa01b8 0xa0384
dump "DISPATCH SERIAL QUEUE POP unlock and callback" 0xa304c 0xa30bc
dump "DISPATCH CONCURRENT QUEUE DRAIN comparison" 0xa058c 0xa06e8
dump "HTTP MESSAGE COMPLETE callback then message release" 0xa4c18 0xa4c64
dump "HTTP CLIENT ERROR HANDLER pending message drain" 0xa4d7c 0xa4f2c
dump "HTTP CLIENT INVALIDATION callback and release" 0xa4f30 0xa4f60
dump "HTTP CLIENT INVALIDATE enqueues callback" 0xa6584 0xa65bc
dump "HTTP ENQUEUE HANDOFF client releases" 0xa6040 0xa6078
dump "CAR GLOBAL CLIENT INVALIDATION" 0x2a74c 0x2a7a8
ARM_READ_ONLY

# Verify the intended disassembly entrypoints were actually captured.
for address in a01b8 a304c a058c a4c18 a4d7c a4f30 a6584 a6040; do
    if ! grep -Eq "^[[:space:]]*0*${address}:" "$TEMP_REPORT"; then
        echo "FAIL: missing ARM function at 0x$address; report preserved" >&2
        exit 1
    fi
done
mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 132 verified-stock queue and cancellation report at $REPORT"
echo "No firmware was modified, packaged, installed or flashed."
