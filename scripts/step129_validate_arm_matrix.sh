#!/usr/bin/env bash
# Compile-only ARM926EJ-S/uClibc matrix. NEVER patches or packages sdDongle.
# Intended for Mac with the known ak3918-buildroot:latest Docker image.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v docker >/dev/null 2>&1 || {
  echo "FAIL: Docker unavailable" >&2
  exit 1
}
test -f "$HERE/altscreen.c" || {
  echo "FAIL: missing altscreen.c" >&2
  exit 1
}
TEMP="$(mktemp -d "${TMPDIR:-/tmp}/ak3918-step129-arm.XXXXXXXX")"
trap 'rm -rf "$TEMP"' EXIT

echo "Compiling 4 experimental source variants, without firmware image or tar."
docker run --rm --platform linux/arm64 -i \
  -v "$HERE:/repo:ro" \
  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
  -v "$TEMP:/out:rw" \
  --entrypoint /bin/bash \
  ak3918-buildroot:latest -s <<'ARM_MATRIX'
set -euo pipefail
PREFIX=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi
CC="${PREFIX}-gcc"
READELF="${PREFIX}-readelf"
test -x "$CC"
test -x "$READELF"
for combined in 0 1; do
  for phone in 0 1; do
    output="/out/libSdH_combined${combined}_phone${phone}.so"
    echo "BUILD ARM/uClibc combined=${combined} phone=${phone}"
    "$CC" -mcpu=arm926ej-s -mfloat-abi=soft -shared -fPIC -Os \
      "-DAK_ENABLE_COMBINED_CLUSTER=${combined}" \
      "-DAK_ENABLE_PHONE_CMDS=${phone}" \
      -fno-unwind-tables -fno-asynchronous-unwind-tables \
      -Wl,-soname,libSdH.so -o "$output" /repo/altscreen.c -lpthread

    "$READELF" -h "$output" > /out/arm_header.txt
    "$READELF" -d "$output" > /out/arm_dynamic.txt
    "$READELF" -sW "$output" > /out/arm_symbols.txt
    grep -q 'Class:.*ELF32' /out/arm_header.txt
    grep -q 'Machine:.*ARM' /out/arm_header.txt
    grep -q 'soft-float ABI' /out/arm_header.txt
    grep -q 'Shared library: \[libc.so.0\]' /out/arm_dynamic.txt
    grep -q 'Library soname: \[libSdH.so\]' /out/arm_dynamic.txt
    grep -q 'INIT_ARRAY' /out/arm_dynamic.txt
    grep -q 'shim_session_setup' /out/arm_symbols.txt
    if [ "$combined" = 1 ]; then
      grep -q 'shim_screen_ensure_stream' /out/arm_symbols.txt
      grep -q 'shim_screen_http_send' /out/arm_symbols.txt
    fi
    echo "PASS ARM/uClibc combined=${combined} phone=${phone}"
  done
done
ARM_MATRIX

echo "PASS: four ARM/uClibc source-only builds validated."
echo "No binaries, recovery firmware or tar files were changed in repository."
