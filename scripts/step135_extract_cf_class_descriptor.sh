#!/usr/bin/env bash
# Step 135 — verify exact stock sdDongle and read the HTTP-client class record.
# This does NOT modify the ELF or produce, install, or flash firmware.
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
REPORT="${1:-$HOME/Desktop/AK3918_step135_cf_class_descriptor.txt}"
EXPECTED=b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1

test -r "$STOCK" || { echo "FAIL: original sdDongle unavailable: $STOCK" >&2; exit 1; }
if command -v shasum >/dev/null 2>&1; then
    ACTUAL="$(shasum -a 256 "$STOCK" | awk '{print $1}')"
else
    ACTUAL="$(sha256sum "$STOCK" | awk '{print $1}')"
fi
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "FAIL: SHA-256 mismatch; refusing to interpret unverified binary" >&2
    exit 1
fi
command -v docker >/dev/null 2>&1 || { echo "FAIL: Docker unavailable" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "FAIL: Python 3 unavailable" >&2; exit 1; }
mkdir -p "$(dirname "$REPORT")"
TEMP_REPORT="$(mktemp "$REPORT.tmp.XXXXXX")"
trap 'rm -f "$TEMP_REPORT"' EXIT

# These fixed ARM opcodes and PC-relative displacements are pinned by Step 133.
# 0xa636c uses PC=0xa6374 and literal 0xa63c4=0x0008eb18:
# candidate CFRuntimeClass address = 0xa6374 + 0x0008eb18 = 0x134e8c.
docker run --rm --platform linux/arm64 -i \
    -v "$ROOT:/repo:ro" \
    -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
    --entrypoint /bin/bash ak3918-buildroot:latest -s > "$TEMP_REPORT" <<'ARM_READ_ONLY'
set -euo pipefail
OB=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi-objdump
RD=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi-readelf
STOCK=/repo/stock_analysis/sdDongle
test -x "$OB"
if [[ ! -x "$RD" ]]; then
    RD="$(command -v readelf)"
fi
test -x "$RD"
test -r "$STOCK"

printf '===== HTTP CLASS REGISTRATION / ONCE CALLBACK =====\n'
"$OB" -d --start-address=0xa6364 --stop-address=0xa641c "$STOCK"
printf '\n===== ELF SECTION/LOAD MAPPINGS =====\n'
"$RD" -SW "$STOCK"
"$RD" -lW "$STOCK"
printf '\n===== CANDIDATE CLASS RECORD VMA RAW BYTES =====\n'
"$OB" -s --start-address=0x134e80 --stop-address=0x134f20 "$STOCK"
printf '\n===== RELOCATION ENTRIES NEAR CANDIDATE CLASS RECORD =====\n'
"$RD" -rW "$STOCK" | awk 'NR < 18 || tolower($0) ~ /00134e[89abcdef][0-9a-f]/ || tolower($0) ~ /00134f[0-9a-f][0-9a-f]/'
printf '\n===== TARGET QUEUE RELEASE AND CLIENT RETAIN CONTEXT =====\n'
"$OB" -d --start-address=0xa0454 --stop-address=0xa0568 "$STOCK"
"$OB" -d --start-address=0xa641c --stop-address=0xa64cc "$STOCK"
ARM_READ_ONLY

python3 - "$TEMP_REPORT" <<'VERIFY_ANCHORS'
import pathlib
import re
import sys

report = pathlib.Path(sys.argv[1]).read_text()
ops = {int(a, 16): opcode.lower() for a, opcode in re.findall(
    r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+", report, re.I | re.M
)}
expected = {
    0xA6368: "e59f0054",
    0xA636C: "e08f0000",
    0xA6370: "ebff78ba",
    0xA63C4: "0008eb18",
    0xA64A4: "e5840008",
    0xA64A8: "ebffe7e9",
}
for addr, encoding in expected.items():
    if ops.get(addr) != encoding:
        raise SystemExit(f"FAIL: stock ARM registration/retain instruction drift at 0x{addr:x}")
descriptor = 0xA636C + 8 + int(ops[0xA63C4], 16)
if descriptor != 0x134E8C:
    raise SystemExit(f"FAIL: class candidate moved to 0x{descriptor:x}")
print("PASS: exact ARM class registration instructions and 0x134e8c candidate")
VERIFY_ANCHORS

{
    echo
    echo "===== ELF32 CLIENT CLASS RECORD DECODE (NOT RELOCATED MEMORY) ====="
    python3 "$HERE/scripts/step135_decode_cf_descriptor.py" "$STOCK" --address 0x134e8c --size 0x80
} >> "$TEMP_REPORT"

mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 135 verified-stock read-only class record report at $REPORT"
echo "NOTE: candidate finalizer identity and release order require manual analysis."
echo "No executable, archive, device setting or recovery firmware changed."
