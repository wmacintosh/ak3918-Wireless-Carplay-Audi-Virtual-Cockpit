#!/usr/bin/env bash
# Step 133: read-only verified-stock dispatch queue lifetime/ownership audit.
# Does not modify sdDongle, Buildroot, firmware archives, or device.
set -euo pipefail

if [[ -n "${AK3918_ROOT:-}" ]]; then
    ROOT="$AK3918_ROOT"
elif [[ -f "$HOME/AK3918_Diagnostics/stock_analysis/sdDongle" ]]; then
    ROOT="$HOME/AK3918_Diagnostics"
else
    ROOT="$HOME/AK3918/01_Development/AK3918_Diagnostics/ak3918-sigsegv-fix"
fi
STOCK="$ROOT/stock_analysis/sdDongle"
REPORT="${1:-$HOME/Desktop/AK3918_step133_queue_ownership.txt}"
EXPECTED=b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1
if [[ ! -f "$STOCK" ]]; then
    echo "FAIL: verified stock executable not found: $STOCK" >&2
    exit 1
fi
if command -v shasum >/dev/null 2>&1; then
    ACTUAL="$(shasum -a 256 "$STOCK" | awk '{print $1}')"
else
    ACTUAL="$(sha256sum "$STOCK" | awk '{print $1}')"
fi
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "FAIL: stock SHA-256 mismatch; refusing unverified queue analysis" >&2
    exit 1
fi
command -v docker >/dev/null 2>&1 || {
    echo "FAIL: Docker unavailable" >&2
    exit 1
}
command -v python3 >/dev/null 2>&1 || {
    echo "FAIL: Python 3 unavailable" >&2
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
# Distinguish the ref-counted queue object from 12-byte queued work nodes.
dump "QUEUE OBJECT REFCOUNT AND FINAL FREE"           0x9fff0 0xa01b8
dump "QUEUE OBJECT DESTRUCTOR NONEMPTY ASSERTION"    0xa01b8 0xa0384
dump "QUEUE SCHEDULING AND WAKE HELPERS"              0xa0384 0xa058c
dump "ASYNC FUNCTION QUEUE NODE ENQUEUE"              0xa1900 0xa1b20
dump "SERIAL QUEUE DISPATCH POP AND CALLBACK"         0xa3000 0xa30c0
dump "QUEUE CREATOR AND ATTACHMENT HELPER"            0xa3180 0xa3480
dump "HTTP CLIENT CONSTRUCTOR AND RELEASE NEIGHBORS" 0xa6000 0xa641c
dump "HTTP CLIENT INIT QUEUE ASSIGNMENT"              0xa641c 0xa6510
dump "HTTP CLIENT FINALIZER AND INVALIDATION"        0xa6510 0xa65bc
dump "HTTP SEND USE OF CLIENT QUEUE"                  0xa6974 0xa6a80
dump "HTTP INVALIDATION MESSAGE DRAIN"               0xa4d7c 0xa4f50
dump "CAR GLOBAL HTTP CLIENT INVALIDATION"           0x2a76c 0x2a7a8
ARM_READ_ONLY

python3 - "$TEMP_REPORT" <<'CHECK_REPORT'
import pathlib
import re
import sys
report = pathlib.Path(sys.argv[1]).read_text()
sections = re.findall(r"^===== (.+?) =====$", report, re.M)
if len(sections) != 12 or len(set(sections)) != 12:
    raise SystemExit("FAIL: Step 133 expected 12 distinct disassembly sections")
required = {
    0xA01B8, 0xA1900, 0xA304C, 0xA32B0, 0xA641C, 0xA64A0,
    0xA64A4, 0xA6584, 0xA6974, 0xA6A68, 0xA6A6C, 0x2A78C,
}
opcodes = {int(addr, 16): opcode.lower()
           for addr, opcode in re.findall(
               r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+", report, re.I | re.M)}
missing = sorted(required - opcodes.keys())
if missing:
    raise SystemExit("FAIL: missing critical stock addresses: " +
                     ", ".join(hex(x) for x in missing))
expected = {
    0xA64A0: "ebfff382",  # client constructor: queue helper
    0xA64A4: "e5840008",  # store queue pointer to client+8
    0xA6A68: "e5960008",  # send: load client+8
    0xA6A6C: "ebffeba3",  # send: dispatch_async_f
}
for addr, opcode in expected.items():
    if opcodes[addr] != opcode:
        raise SystemExit(f"FAIL: unexpected native ARM opcode at {addr:#x}: "
                         f"{opcodes[addr]} (expected {opcode})")
print("PASS: verified-stock queue constructor/assignment/send callsites captured")
print("NOTE: queue lifetime and destruction ordering still require analysis")
CHECK_REPORT

mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 133 read-only queue ownership report at $REPORT"
echo "No executable, archive, device setting or recovery firmware changed."
