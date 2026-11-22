#!/usr/bin/env bash
# Step 134: read-only verified-stock HTTP client CF finalizer/global queue audit.
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
REPORT="${1:-$HOME/Desktop/AK3918_step134_client_finalizer.txt}"
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
# Locate CF runtime class registration, HTTP-client object finalizer and
# its queue release; separately inspect process-global queue retirement.
# No write, patch, package, installation or device interaction is performed.
dump "CF RUNTIME CREATE AND REGISTER CONTEXT"          0x84640 0x84720
dump "HTTP CLASS REGISTER AND QUEUE OWNER SETUP"      0xa6364 0xa6510
dump "HTTP CLIENT CREATE AND INVALIDATION"           0xa6510 0xa65d0
dump "HTTP EARLY FINALIZER CANDIDATES"                0xa4f30 0xa5180
dump "HTTP STATE MACHINE AND RELATED FINALIZERS"      0xa5180 0xa5400
dump "HTTP DISPATCH HANDOFF AND CLIENT RELEASE"       0xa6040 0xa6078
dump "GLOBAL QUEUE ACCESS AND RETIREMENT"             0xa32b0 0xa3448
dump "DISPATCH GLOBAL INITIALIZATION"                 0xa1d80 0xa1f80
dump "DISPATCH OBJECT RETAIN AND RELEASE"             0xa0454 0xa0568
dump "DISPATCH ASYNC NODE ENQUEUE"                    0xa1900 0xa1b20
dump "DISPATCH SERIAL CALLBACK AND QUEUE RELEASE"    0xa3040 0xa30bc
dump "CAR-SIDE GLOBAL CLIENT INVALIDATE RELEASE"     0x2a76c 0x2a7b0
dump "HTTP CLIENT MESSAGE DRAIN"                      0xa4d7c 0xa4f50

# These are only cross-reference HINTS. Register values and CF callback
# descriptor memory must be inspected before assigning finalizer ownership.
printf '\n===== HTTP MODULE CALLS INTO QUEUE REF AND ENQUEUE HELPERS =====\n'
"$OBJDUMP" -d --start-address=0xa4000 --stop-address=0xa6b00 "$STOCK" |
  awk '/[[:space:]](bl|b)[[:space:]]+[0-9a-f]+[[:space:]]+<.*(\+0x138>|\+0xd0>|\+0x1218>)/ || /[[:space:]](bl|b)[[:space:]]+(a04bc|a0454|a1900)[[:space:]]/ {print}'
ARM_READ_ONLY

python3 - "$TEMP_REPORT" <<'CHECK_REPORT'
import pathlib
import re
import sys
report = pathlib.Path(sys.argv[1]).read_text()
sections = re.findall(r"^===== (.+?) =====$", report, re.M)
if len(sections) != 14 or len(set(sections)) != 14:
    raise SystemExit("FAIL: Step 134 expected 14 distinct disassembly sections")
required = {
    0x84660, 0xA63D8, 0xA641C, 0xA64A4, 0xA64A8,
    0xA6584, 0xA4F30, 0xA6040, 0xA32B0, 0xA33B4, 0xA342C,
    0xA0454, 0xA04BC, 0xA1900, 0xA1980, 0xA308C, 0xA30A4,
    0x2A78C, 0xA4D7C,
}
opcodes = {int(addr, 16): opcode.lower()
           for addr, opcode in re.findall(
               r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+", report, re.I | re.M)}
missing = sorted(required - opcodes.keys())
if missing:
    raise SystemExit("FAIL: missing critical stock addresses: " +
                     ", ".join(hex(x) for x in missing))
expected = {
    0xA64A4: "e5840008",  # store queue pointer to client+8
    0xA64A8: "ebffe7e9",  # retain client-held queue
    0xA342C: "eafff361",  # global queue retirement tail to destructor
    0xA30A4: "ebfff504",  # last queued callback releases work-held queue
}
for addr, opcode in expected.items():
    if opcodes[addr] != opcode:
        raise SystemExit(f"FAIL: unexpected native ARM opcode at {addr:#x}: "
                         f"{opcodes[addr]} (expected {opcode})")
print("PASS: stock client queue retain and global queue retirement anchors captured")
print("NOTE: finalizer identity and shutdown guarantees require manual control-flow analysis")
CHECK_REPORT

mv "$TEMP_REPORT" "$REPORT"
echo "PASS: Step 134 read-only client finalizer report at $REPORT"
echo "No executable, archive, device setting or recovery firmware changed."
