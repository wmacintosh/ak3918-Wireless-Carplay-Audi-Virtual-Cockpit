#!/usr/bin/env bash
# Step 125: read-only native HTTP transport and callback disassembly.
set -euo pipefail

# The verified stock binary lives in the local diagnostics folder, not GitHub.
# Prefer the location used in the recent Mac sessions; allow an explicit override.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${AK3918_ROOT:-}" ]]; then
    ROOT="$AK3918_ROOT"
elif [[ -f "$HOME/AK3918_Diagnostics/stock_analysis/sdDongle" ]]; then
    ROOT="$HOME/AK3918_Diagnostics"
else
    ROOT="$HOME/AK3918/01_Development/AK3918_Diagnostics/ak3918-sigsegv-fix"
fi
STOCK="$ROOT/stock_analysis/sdDongle"
REPORT="${1:-$HOME/Desktop/AK3918_step125_native_http_transport.txt}"
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

# Preserve an earlier valid report if the container fails or exits early.
TEMP_REPORT="$(mktemp "$REPORT.tmp.XXXXXX")"
trap 'rm -f "$TEMP_REPORT"' EXIT

echo "PASS: Verified stock ELF; extracting read-only transport control flow"
# Literal heredoc prevents apostrophes in comments from ending the container
# script early. Both firmware and toolchain mounts are read-only.
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
# HTTP send can queue an asynchronous callback or trigger teardown.
# Extract the relevant stock functions before changing synchronization.
dump "HTTP SEND ENTRY" 0xa6974 0xa6a98
dump "HTTP TRANSPORT REGISTRATION" 0xa18c0 0xa1b80
dump "NATIVE SCREEN SETUP RESPONSE CALLBACK" 0x2ec60 0x2ef80
dump "RECEIVER SESSION FINALIZER" 0x669e0 0x66c00
dump "NATIVE HTTP MESSAGE CREATION" 0xa6d08 0xa6e50
AK3918_READONLY

if [[ ! -s "$TEMP_REPORT" ]] ||
   ! grep -Eq '^[[:space:]]*0*a6974:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*a1900:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*2ec7c:' "$TEMP_REPORT" ||
   ! grep -Eq '^[[:space:]]*0*66a40:' "$TEMP_REPORT"; then
    echo "FAIL: Incomplete native transport audit: expected ARM entrypoints missing." >&2
    exit 1
fi
mv "$TEMP_REPORT" "$REPORT"

echo "PASS: Step 125 report created at $REPORT"
ls -lh "$REPORT"
echo "No firmware was modified, packaged, or installed."

# No post-processing until the native transport/dispatch call graph is audited.
echo "Source-only evidence; HTTP callback reentrancy remains unverified."
