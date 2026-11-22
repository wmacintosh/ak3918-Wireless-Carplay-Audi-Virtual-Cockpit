#!/usr/bin/env bash
# Build an explicitly requested experimental stream111 archive; never contact device.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$HOME/Desktop/AK3918_Stream111_Test}"
EXPECTED_BRANCH="wip/ak3918-step115-callback-tombstones"
command -v docker >/dev/null || { echo "FAIL CLOSED: Docker unavailable"; exit 2; }
command -v python3 >/dev/null || { echo "FAIL CLOSED: Python3 unavailable"; exit 2; }
[[ -d "$(dirname "$OUT")" && ! -e "$OUT" ]] || {
  echo "FAIL CLOSED: output directory exists or parent missing: $OUT"; exit 2;
}
cd "$ROOT"
[[ "$(git branch --show-current)" == "$EXPECTED_BRANCH" ]] || {
  echo "FAIL CLOSED: not on exact WIP branch"; exit 2;
}
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "FAIL CLOSED: tracked files modified"; exit 2;
}
COMMIT="$(git rev-parse HEAD)"
[[ "$COMMIT" =~ ^[a-f0-9]{40}$ ]] || { echo "FAIL CLOSED: invalid commit"; exit 2; }

echo "===== ORIGINAL STOCK + RECOVERY PRE-FLIGHT ====="
AK_ENABLE_COMBINED_CLUSTER=1 \
AK_ENABLE_PHONE_CMDS=1 \
AK_STEP128_ALLOW_TEST_PACKAGE=1 \
AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=0 \
python3 scripts/step141_readonly_firmware_preflight.py

STAGE="$(mktemp -d "$HOME/Desktop/.ak3918-step147.XXXXXXXX")"
cleanup() { [[ -z "${STAGE:-}" || ! -e "$STAGE" ]] || rm -rf "$STAGE"; }
trap cleanup EXIT
echo "===== ISOLATED ARM BUILD, FULL ELF AUDIT, TEST TAR ====="
docker run --rm --pull never --network none --platform linux/arm64 -i \
  -v "$ROOT:/repo:ro" \
  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
  -v "$STAGE:/out:rw" \
  -e AK_SOURCE_COMMIT="$COMMIT" \
  --entrypoint /bin/bash ak3918-buildroot:latest -s <<'BUILD147'
set -euo pipefail
PREFIX=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi
test -x "${PREFIX}-gcc"
WORK="$(mktemp -d /tmp/ak3918-step147-build.XXXXXXXX)"
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/extracted" "$WORK/modified"
cp /repo/build_hook.py /repo/repair_elf.py /repo/altscreen.c "$WORK/"
for name in sdDongle libSdAuto.so libSdCommon.so libSdSampleRate.so libSdUtils.so; do
  cp "/repo/extracted/$name" "$WORK/extracted/$name"
done
cd "$WORK"
export AK_ENABLE_COMBINED_CLUSTER=1
export AK_ENABLE_PHONE_CMDS=1
export AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=0
export AK_STEP128_ALLOW_TEST_PACKAGE=1
export AK_UCLIBC_CC="${PREFIX}-gcc"
python3 - <<'PYBUILD'
import build_hook
if not build_hook.ENABLE_COMBINED_CLUSTER or not build_hook.ENABLE_PHONE_CMDS:
    raise SystemExit("REFUSE: both experimental features required")
if build_hook.package_plan()!="ak_hook_step128_test.tar":
    raise SystemExit("REFUSE: wrong experimental package plan")
build_hook.main()
PYBUILD

python3 /repo/scripts/step142_audit_patched_elf.py \
  "$WORK/extracted/sdDongle" "$WORK/modified/sdDongle" \
  "$WORK/modified/libSdH.so" "$PREFIX"

python3 - <<'PYMANIFEST'
from pathlib import Path
import hashlib,json,os,sys,shutil
sys.path.insert(0,"/repo/scripts")
from step147_validate_experimental_package import (
    PACKAGE_NAME,MANIFEST_NAME,EXPECTED,EXPECTED_BRANCH,
    EXPECTED_SYSTEM_VERSION,EXPECTED_PROTOCOL_VERSION,validate
)
p=Path(PACKAGE_NAME)
if not p.is_file():
    raise SystemExit("REFUSE: builder produced no test archive")
for name, expected in EXPECTED.items():
    path=Path("modified")/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise SystemExit("REFUSE: compiled/patched ELF or vendor lib differs: "+name)
record={
    "format":"ak3918-step147-stream111-test-v1",
    "package":PACKAGE_NAME,
    "sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
    "branch":EXPECTED_BRANCH,
    "commit":os.environ["AK_SOURCE_COMMIT"],
    "features":{"AK_ENABLE_COMBINED_CLUSTER":1,"AK_ENABLE_PHONE_CMDS":1},
    "system_version":EXPECTED_SYSTEM_VERSION,
    "protocol_version":EXPECTED_PROTOCOL_VERSION,
    "members":EXPECTED,
}
m=Path(MANIFEST_NAME)
m.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
validate(p,m)
print("PASS: verified 6-member package and exact build hashes")
shutil.copyfile(p,Path("/out")/PACKAGE_NAME)
shutil.copyfile(m,Path("/out")/MANIFEST_NAME)
PYMANIFEST
BUILD147

echo "===== MAC-SIDE INDEPENDENT TAR VALIDATION ====="
python3 scripts/step147_validate_experimental_package.py \
  "$STAGE/ak_hook_step128_test.tar" "$STAGE/step147-manifest.json"
mv "$STAGE" "$OUT"
STAGE=""
echo "PASS: STEP147 TEST PACKAGE PREPARED"
echo "SOURCE_COMMIT=$COMMIT"
echo "PACKAGE=$OUT/ak_hook_step128_test.tar"
echo "MANIFEST=$OUT/step147-manifest.json"
echo "NOT INSTALLED: actual target libc and hardware unbrick remain unverified."
