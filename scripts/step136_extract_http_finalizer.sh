#!/usr/bin/env bash
# Step 136: read-only finalizer candidate 0xa4b08 and queue-release audit.
# Original stock ELF ONLY: no modifications, package generation, or flashing.
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
REPORT="${1:-$HOME/Desktop/AK3918_step136_http_finalizer.txt}"
EXPECTED=b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1

test -r "$STOCK" || { echo "FAIL: verified stock ELF not found: $STOCK" >&2; exit 1; }
if command -v shasum >/dev/null 2>&1; then
    ACTUAL="$(shasum -a 256 "$STOCK" | awk '{print $1}')"
else
    ACTUAL="$(sha256sum "$STOCK" | awk '{print $1}')"
fi
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "FAIL: refusing unverified stock ELF checksum" >&2
    exit 1
fi
command -v docker >/dev/null 2>&1 || { echo "FAIL: Docker unavailable" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "FAIL: Python 3 unavailable" >&2; exit 1; }
mkdir -p "$(dirname "$REPORT")"
TEMP_REPORT="$(mktemp "$REPORT.tmp.XXXXXX")"
trap 'rm -f "$TEMP_REPORT"' EXIT

# Independently verify the CLASS RECORD using raw ELF32 program headers.
# Standard 32-bit CFRuntimeClass fields: version, name, init, copy, finalize.
# The reported +0x10 callback remains a candidate pending native code review.
PYTHONPATH="$HERE/scripts" python3 - "$STOCK" <<'VERIFY_CLASS_RECORD'
from pathlib import Path
from step135_decode_cf_descriptor import read_image
import struct, sys
blob = Path(sys.argv[1]).read_bytes()
record, segment = read_image(blob, 0x134e8c, 0x2c)
if record is None:
    raise SystemExit(f"FAIL: class record missing: {segment}")
fields = struct.unpack("<5I", record[:20])
if fields != (0, 0x0010abbe, 0, 0, 0x000a4b08):
    raise SystemExit(f"FAIL: unexpected stock class callback fields: {fields!r}")
name, location = read_image(blob, fields[1], 96)
if name is None:
    raise SystemExit(f"FAIL: class name not file backed: {location}")
raw_name = name.split(b"\x00", 1)[0]
if not raw_name or len(raw_name) > 80:
    raise SystemExit("FAIL: class name missing or unexpectedly long")
print(f"PASS: stock class record finalize candidate 0x{fields[4]:x} at +0x10; name={raw_name!r}")
VERIFY_CLASS_RECORD

docker run --rm --platform linux/arm64 -i \
  -v "$ROOT:/repo:ro" \
  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
  --entrypoint /bin/bash ak3918-buildroot:latest -s > "$TEMP_REPORT" <<'ARM_READ_ONLY'
set -euo pipefail
OB=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi-objdump
RD=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi-readelf
STOCK=/repo/stock_analysis/sdDongle
test -x "$OB"
if [[ ! -x "$RD" ]]; then RD="$(command -v readelf)"; fi
test -x "$RD"
test -r "$STOCK"
dump() {
    printf '\n===== %s =====\n' "$1"
    "$OB" -d --start-address="$2" --stop-address="$3" "$STOCK"
}

dump "HTTP CLIENT CLASS FINALIZER CANDIDATE AND NEIGHBORS" 0xa4a10 0xa4c18
dump "HTTP MESSAGE COMPLETION AND CALLBACK" 0xa4c18 0xa4c64
dump "HTTP CLIENT ERROR DRAIN AND RELEASE" 0xa4d7c 0xa4f50
dump "NATIVE QUEUE RETAIN AND RELEASE" 0xa0454 0xa0568
dump "HTTP CLASS INIT AND QUEUE RETAIN" 0xa6364 0xa64cc
dump "CF RUNTIME REGISTER AND OBJECT CREATE" 0x84640 0x84720
dump "HTTP CLIENT SEND WORK HANDOFF" 0xa6040 0xa6078
dump "SERIAL DISPATCH LAST WORK RELEASE" 0xa3040 0xa30bc
dump "GLOBAL DISPATCH QUEUE RETIREMENT" 0xa33b4 0xa3448
dump "CAR SIDE HTTP CLIENT INVALIDATE RELEASE" 0x2a76c 0x2a7b0

printf '\n===== RECORD BYTES 0x134e8c AND NEIGHBOR DESCRIPTORS =====\n'
"$OB" -s --start-address=0x134e80 --stop-address=0x134ed0 "$STOCK"
printf '\n===== CLASS NAME STRING SOURCE =====\n'
"$OB" -s --start-address=0x10abb0 --stop-address=0x10ac40 "$STOCK"
printf '\n===== ELF RELOCATION TABLES =====\n'
"$RD" -rW "$STOCK"
ARM_READ_ONLY

python3 - "$TEMP_REPORT" <<'VERIFY_DISASSEMBLY'
import pathlib, re, sys
txt = pathlib.Path(sys.argv[1]).read_text()
sections = re.findall(r"^===== (.+?) =====$",txt,re.M)
if len(sections) != 13 or len(set(sections)) != 13:
    raise SystemExit("FAIL: expected 13 native evidence sections")
ops = {int(address,16):encoding.lower() for address,encoding in
       re.findall(r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+",txt,re.M|re.I)}
for address,encoding in {
    0xa4b08:None,         # Finalizer candidate function start.
    0xa4c4c:"e12fff33",  # Message callback.
    0xa64a4:"e5840008",  # Store queue to client+0x08.
    0xa64a8:"ebffe7e9",  # Client queue retain.
    0xa30a4:"ebfff504",  # Work-queue reference release after dispatch.
}.items():
    found = ops.get(address)
    if found is None or (encoding is not None and found!=encoding):
        raise SystemExit(f"FAIL: required stock ARM instruction at 0x{address:x} unexpected: {found}")
print("PASS: stock finalizer candidate instructions and queue lifecycle anchors captured")
print("NOTE: finalizer queue release and callback lifetime require manual control-flow review")
VERIFY_DISASSEMBLY

mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 136 read-only HTTP finalizer report at $REPORT"
echo "No executable, archive, device setting or recovery firmware changed."
