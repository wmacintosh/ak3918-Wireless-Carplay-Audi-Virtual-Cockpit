#!/usr/bin/env bash
# Step143: OFFLINE exact-stock + CGI recovery + ephemeral ARM symbol audit.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -gt 0 ]; then
    REPORT="$1"
else
    REPORT="$HOME/Desktop/AK3918_step143_loader_recovery_audit.txt"
fi
command -v docker >/dev/null 2>&1 || {
    echo "FAIL CLOSED: Docker unavailable" >&2
    exit 2
}
test -d "$(dirname "$REPORT")" || {
    echo "FAIL CLOSED: report destination directory missing" >&2
    exit 2
}
TEMP="$(mktemp -d "${TMPDIR:-/tmp}/ak3918-step143-report.XXXXXXXX")"
trap 'rm -rf "$TEMP"' EXIT
OUT="$TEMP/result.txt"
{
    echo "STEP 143 DISPOSABLE ARM LOADER SYMBOL AND CGI-RECOVERY AUDIT"
    echo "NO DEVICE NETWORK, NO ARCHIVE UPLOAD, NO PACKAGING OR FLASH"
    printf 'MAC_REPOSITORY=%s\n' "$HERE"
    printf '\n===== REPEAT STOCK INTEGRITY GATE =====\n'
} > "$OUT"
if ! (
    cd "$HERE"
    AK_ENABLE_COMBINED_CLUSTER=1 \
    AK_ENABLE_PHONE_CMDS=1 \
    AK_STEP128_ALLOW_TEST_PACKAGE=1 \
    AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=0 \
    python3 scripts/step141_readonly_firmware_preflight.py
) >> "$OUT" 2>&1; then
    echo "FAIL CLOSED: Step141 original ELF/archival input gate" >> "$OUT"
    cp "$OUT" "$REPORT"; cat "$OUT"; exit 2
fi
echo "===== CGI RECOVERY PATH REVIEW (OFFLINE) =====" >> "$OUT"
if ! (cd "$HERE"; python3 scripts/step143_recovery_readiness.py) >> "$OUT" 2>&1; then
    echo "FAIL CLOSED: Step143 archive/CGI review" >> "$OUT"
    cp "$OUT" "$REPORT"; cat "$OUT"; exit 2
fi
set +e
docker run --rm --pull never --network none --platform linux/arm64 -i \
    -v "$HERE:/repo:ro" \
    -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
    --entrypoint /bin/bash \
    ak3918-buildroot:latest -s >> "$OUT" 2>&1 <<'ELF143'
set -euo pipefail
PREFIX=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi
CC="$PREFIX-gcc"
RE="$PREFIX-readelf"
test -x "$CC" && test -x "$RE"
WORK="$(mktemp -d /tmp/ak3918-step143-disposable.XXXXXXXX)"
trap 'rm -rf "$WORK"' EXIT
cp /repo/altscreen.c /repo/build_hook.py "$WORK/"
cd "$WORK"
export AK_UCLIBC_CC="$CC"
export AK_ENABLE_COMBINED_CLUSTER=1
export AK_ENABLE_PHONE_CMDS=1
export AK_STEP128_ALLOW_TEST_PACKAGE=0
export AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=0
echo "===== EPHEMERAL ARM HOOK BUILD, NO FIRMWARE PATCH ====="
python3 - <<'PYBUILD'
import build_hook
if build_hook.package_plan() is not None:
    raise SystemExit("FAIL CLOSED: non-null package plan")
build_hook.build_shim("libSdH.so")
print("PASS: disposable ARM shared library built without firmware packaging")
PYBUILD

SYSROOT="$("$CC" -print-sysroot)"
if [ ! -d "$SYSROOT" ]; then
    SYSROOT=/workspace/buildroot-work/buildroot/output/staging
fi
LIBC=""
PTHREAD=""
if [ -d "$SYSROOT" ]; then
    LIBC="$(find "$SYSROOT" -name libc.so.0 -print -quit)"
    PTHREAD="$(find "$SYSROOT" -name libpthread.so.0 -print -quit)"
fi
printf 'TOOLCHAIN_SYSROOT=%s\n' "$SYSROOT"
if [ -n "$LIBC" ]; then printf 'TOOLCHAIN_LIBC=%s\n' "$LIBC"; fi
if [ -n "$PTHREAD" ]; then printf 'TOOLCHAIN_LIBPTHREAD=%s\n' "$PTHREAD"; fi
args=(
    --reader "$RE"
    --hook "$WORK/libSdH.so"
    --stock /repo/extracted/sdDongle
    --vendor /repo/extracted/libSdAuto.so
    --vendor /repo/extracted/libSdCommon.so
    --vendor /repo/extracted/libSdSampleRate.so
    --vendor /repo/extracted/libSdUtils.so
)
if [ -n "$LIBC" ]; then args+=(--sysroot-libc "$LIBC"); fi
if [ -n "$PTHREAD" ]; then args+=(--sysroot-pthread "$PTHREAD"); fi
echo "===== OFFLINE PROVIDER SYMBOL AUDIT ====="
python3 /repo/scripts/step143_audit_loader_symbols.py "${args[@]}"
echo "PASS: STEP143 OFFLINE SYMBOL AND CGI AUDITS COMPLETE"
echo "NOT VERIFIED: actual target libraries/loader, hardware unbrick or video"
ELF143
RC="$?"
set -e
if [ "$RC" != 0 ]; then
    printf 'FAIL CLOSED: Step143 Docker audit failed (rc=%s)\n' "$RC" >> "$OUT"
fi
cp "$OUT" "$REPORT"
cat "$OUT"
if [ "$RC" != 0 ]; then
    echo "NO FIRMWARE ARCHIVE, FLASH OR DEVICE ACTION PERFORMED"
    exit 2
fi
echo "PASS: Step143 report saved: $REPORT"
echo "BLOCKED FOR FLASH: device loader and independent recovery not yet verified."
