#!/usr/bin/env bash
# Step 142: build & audit experimental ARM ELF INSIDE DISPOSABLE Docker workspace.
# No patch/build outputs are written into the repo, no firmware tar is created,
# and the container has NO NETWORK; this script never contacts the dongle.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="${1:-$HOME/Desktop/AK3918_step142_isolated_elf_audit.txt}"

command -v docker >/dev/null 2>&1 || {
  echo "FAIL CLOSED: Docker is required for isolated ARM/uClibc audit" >&2
  exit 2
}
command -v python3 >/dev/null 2>&1 || {
  echo "FAIL CLOSED: host Python3 unavailable" >&2
  exit 2
}
test -d "$HERE/extracted" || {
  echo "FAIL CLOSED: missing original extracted/ inputs; run Step141 verified staging" >&2
  exit 2
}
test -d "$(dirname "$REPORT")" || {
  echo "FAIL CLOSED: report destination directory missing" >&2
  exit 2
}

TEMP="$(mktemp -d "${TMPDIR:-/tmp}/ak3918-step142-audit.XXXXXXXX")"
trap 'rm -rf "$TEMP"' EXIT
RESULT="$TEMP/result.txt"
{
  echo "STEP 142 ISOLATED ARM ELF BUILD AND STATIC AUDIT"
  echo "This process NEVER packages or flashes firmware."
  echo "The repo and Buildroot toolchain are mounted read-only."
  echo "The Docker container has --network none and does not keep any compiled image."
  printf 'MAC_REPOSITORY=%s\n' "$HERE"
  printf '\n===== REPEAT VERIFIED-STOCK STEP 141 INPUT PREFLIGHT =====\n'
} > "$RESULT"

if ! (
  cd "$HERE"
  AK_ENABLE_COMBINED_CLUSTER=1 \
  AK_ENABLE_PHONE_CMDS=1 \
  AK_STEP128_ALLOW_TEST_PACKAGE=1 \
  AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=0 \
  python3 scripts/step141_readonly_firmware_preflight.py
) >> "$RESULT" 2>&1; then
  {
    echo "FAIL CLOSED: Step141 local preflight failed; no Docker build attempted."
    echo "NO ARCHIVE, FLASH, NETWORK OR DEVICE ACTION PERFORMED"
  } >> "$RESULT"
  cp "$RESULT" "$REPORT"
  cat "$RESULT"
  exit 2
fi

# This Docker run only sees verified original inputs via a READ-ONLY mount.
# The compiler, patcher and repair run in a temporary container directory.
# The modified ELF and .so are NEVER mounted onto the host, only audit text.
set +e
docker run --rm --pull never --network none --platform linux/arm64 -i \
  -v "$HERE:/repo:ro" \
  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
  --entrypoint /bin/bash \
  ak3918-buildroot:latest -s >> "$RESULT" 2>&1 <<'DISPOSABLE_ELF_AUDIT'
set -euo pipefail
PREFIX=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi
CC="${PREFIX}-gcc"
RD="${PREFIX}-readelf"
OB="${PREFIX}-objdump"
test -x "$CC" && test -x "$RD" && test -x "$OB"
command -v python3
command -v readelf
WORK="$(mktemp -d /tmp/ak3918-step142-disposable.XXXXXXXX)"
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/extracted" "$WORK/modified"
cp /repo/build_hook.py /repo/repair_elf.py /repo/altscreen.c "$WORK/"
for name in sdDongle libSdAuto.so libSdCommon.so libSdSampleRate.so libSdUtils.so; do
    cp "/repo/extracted/$name" "$WORK/extracted/$name"
done
cd "$WORK"

# Do not invoke builder.main() or make_tar(); package_plan() must be NONE.
export AK_ENABLE_COMBINED_CLUSTER=1
export AK_ENABLE_PHONE_CMDS=1
export AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=0
export AK_STEP128_ALLOW_TEST_PACKAGE=0
export AK_UCLIBC_CC="$CC"
printf '\n===== BUILD ARM/uClibc 111+PHONE SHIM AND PATCH COPIED STOCK ELF =====\n'
python3 - <<'PYBUILD'
import hashlib
import build_hook
from repair_elf import repair

if build_hook.package_plan() is not None:
    raise SystemExit("FAIL CLOSED: package plan is not None")
print("PASS: builder package_plan() is None; no tar generation")
source="extracted/sdDongle"
blob=open(source,"rb").read()
digest=hashlib.sha256(blob).hexdigest()
if digest!="b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1":
    raise SystemExit("FAIL CLOSED: original stock ELF SHA mismatch")
build_hook.build_shim("modified/libSdH.so")
build_hook.patch_sddongle(source,"modified/sdDongle")
print("REPAIR RESULT:",repair("modified/sdDongle"))
print("PASS: compiled and repaired ephemeral copies only")
PYBUILD

printf '\n===== STATIC AUDIT OF ACTUAL REPAIRED ELF AND LIBRARY =====\n'
python3 /repo/scripts/step142_audit_patched_elf.py \
    "$WORK/extracted/sdDongle" "$WORK/modified/sdDongle" \
    "$WORK/modified/libSdH.so" "$PREFIX"

printf '\n===== PATCHED ELF PROGRAM HEADERS =====\n'
"$RD" -lW "$WORK/modified/sdDongle"
printf '\n===== PATCHED ELF DYNAMIC TAGS =====\n'
"$RD" -dW "$WORK/modified/sdDongle"
printf '\n===== PATCHED ELF RELOCATIONS =====\n'
"$RD" -rW "$WORK/modified/sdDongle"
printf '\n===== SHIM DYNAMIC LIBRARY HEADERS =====\n'
"$RD" -h "$WORK/modified/libSdH.so"
printf '\n===== SHIM IMPORTS AND SONAME =====\n'
"$RD" -dW "$WORK/modified/libSdH.so"
printf '\n===== SHIM EXPORTED AND UNRESOLVED SYMBOLS =====\n'
"$RD" -sW "$WORK/modified/libSdH.so" \
  | grep -E 'shim_|UND |GetStreamKeys|pthread|libSdH|GLIBC|sd' | head -160 || true

echo "PASS: STEP142 ISOLATED ARM/uClibc ELF AUDIT COMPLETED"
echo "No firmware tar, device upload, flash, or persistent patched executable created."
DISPOSABLE_ELF_AUDIT
RC=$?
set -e
if [[ "$RC" != 0 ]]; then
  {
    echo "FAIL CLOSED: Step142 isolated ELF compile or structural audit failed (Docker rc=$RC)"
    echo "NO ARCHIVE, FLASH, NETWORK OR DEVICE ACTION PERFORMED"
  } >> "$RESULT"
fi

cp "$RESULT" "$REPORT"
cat "$RESULT"
if [[ "$RC" != 0 ]]; then
  exit 2
fi
echo "PASS: Step142 audit report saved: $REPORT"
echo "BLOCKED FOR FLASH: a green static ELF audit does not prove device runtime or recovery."
