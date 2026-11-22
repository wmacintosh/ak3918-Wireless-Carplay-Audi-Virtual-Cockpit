# Step 141 — Experimental stream-111 pre-flash integrity and recovery gate

**Status: offline, read-only preflight only; no executable, recovery tar or device setting changed. No target firmware built, patched, packaged, installed, uploaded or flashed.** The combined stream-111 branch is **not yet cleared for hardware installation**.

## Why this step exists

The historical `flash_ak.py` reads **`ak_hook.tar`** for a patched installation and **`stock_ak_202610081659.tar`** for `--stock`. It cannot select `ak_hook_step128_test.tar` from the current experimental branch. Running `python3 flash_ak.py` now would install the *historical* image, not the current combined + phone-command code. Renaming the experimental image to `ak_hook.tar` would bypass the repository's deliberately separated archive names and is not an approved workaround.

The current `build_hook.py` uses opt-in flags to create `ak_hook_step128_test.tar` and requires original `extracted/sdDongle`, four original library inputs and an ARM926EJ-S/uClibc cross-compiler. The host-only Step 140 passing suite is not an end-to-end dongle/vehicle test. A green CI does not verify the actual patched executable, native loader imports, real asynchronous session lifetime or physical recovery.

## Script added

`scripts/step141_readonly_firmware_preflight.py` checks the *input* assumptions without writing files:

1. Ensures the working tree is clean and checked out at `wip/ak3918-step115-callback-tombstones`, and that flags select both experimental features and the distinct test-only package plan.
2. Reads the original `extracted/sdDongle` and insists on SHA-256 **`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`**.
3. Validates ELF32/little-endian ARM/EXEC and the original instruction words at `0x5ec50`, `0x2fadc`, `0x2fbb0`, all five historical display patch locations, class name, original session finalizer, `.bss` boundaries, dynamic null slots and GNU RELRO containing the finalizer field.
4. **Simulates in memory only** the original patcher's zero-gap search for the setup, finalizer and two combined screen trampolines, enforcing alignment, non-overlap, executable-mapped space and ARM branch range. No on-disk patching.
5. Reads historical **`stock_ak_202610081659.tar`**, requires the known SHA-256 **`a4ee31452833cc38cf4a3839adaa75b9b34fd0a9d2ed006e0c9b34ae7539dba3`**, checks each archive member is safe and present, and verifies that the original stock executable and four original libraries in `extracted/` are byte-for-byte the matching recovery members. The tar is **never extracted** by this script.
6. Confirms the local `flash_ak.py` still targets legacy and stock filenames rather than the experimental archive. It may display whether the `AK_UCLIBC_CC` compiler selector exists, but does not run a compiler.

**NOTE:** a verified recovery `.tar` is a useful prerequisite but **not proof of unbrick capability**. The current `flash_ak.py --stock` relies on the dongle booting far enough to expose Wi-Fi and HTTP CGI endpoints. A broken boot or damaged network service can make that route unavailable. An independently validated hardware/bootloader recovery procedure is still an unresolved requirement before flashing WIP firmware.

## Run the local offline preflight on the Mac

In Terminal, from the current experimental repo:

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
AK_ENABLE_COMBINED_CLUSTER=1 \
AK_ENABLE_PHONE_CMDS=1 \
AK_STEP128_ALLOW_TEST_PACKAGE=1 \
python3 scripts/step141_readonly_firmware_preflight.py \
  | tee "$HOME/Desktop/AK3918_step141_readonly_preflight.txt"
```

The command **does not compile, patch, package, send, install or flash** anything. A PASS merely means the original artifacts and inputs match the assumptions. A FAIL is a real blocker: investigate why the file is absent or the original differs instead of force-updating, substituting a patched image, renaming an archive or ignoring a checksum.

The report printed to `~/Desktop/AK3918_step141_readonly_preflight.txt` can be uploaded for the next review. If the preflight ends `FAIL CLOSED`, the direct pipeline's exit status can be hidden by `tee`. In an interactive bash shell, use `set -o pipefail` before running the command, or inspect the last report line and do not proceed unless the script explicitly prints `PASS: STEP141 OFFLINE STATIC PREFLIGHT`.

## Resolution: missing `extracted/sdDongle` on fresh `git pull`

The user's first Step 141 local run passed Git branch and both feature-flag checks, then failed closed at:

```text
FAIL CLOSED: builder input extracted/sdDongle is missing; do not use modified/sdDongle
```

This is a **missing local build-input staging step**, not a detected ARM mismatch. GitHub tracks the historical `stock_ak_202610081659.tar` but not the unpacked `extracted/` directory. Git cannot restore untracked extracted files through `git pull`.

To resolve that without copying a patched image, run the explicit, safe local staging helper:

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
python3 scripts/step141_stage_verified_stock_inputs.py
```

The helper first validates the complete recovery tar's SHA-256 against the pinned historical digest and checks each of the five named original members. It refuses a recovery tar whose `sdDongle` does not match the original pinned stock ELF digest, verifies all members **before writing**, and refuses to overwrite an existing `extracted/` input that differs. It extracts **only** the five expected regular files, without executing firmware, recursively extracting arbitrary paths, or changing the recovery archive. It may create the local `extracted/` directory and missing members. Unlike the preflight, **this helper intentionally writes these verified local inputs**.

Then re-run the unchanged read-only preflight:

```bash
set -o pipefail
AK_ENABLE_COMBINED_CLUSTER=1 \
AK_ENABLE_PHONE_CMDS=1 \
AK_STEP128_ALLOW_TEST_PACKAGE=1 \
python3 scripts/step141_readonly_firmware_preflight.py \
  | tee "$HOME/Desktop/AK3918_step141_readonly_preflight.txt"
```

The recovery tar is available in the GitHub checkout, but **its internal `sdDongle` is not assumed to match until the explicit SHA/member check passes**. A mismatch is a real blocker: do not substitute `modified/sdDongle`, overwrite a conflicting local input or rename a test package to bypass the source-integrity gate.

The additional `tests/test_step141_stock_input_staging.py` exercises synthetic archive staging/no-overwrite cases and independently checks the tracked real recovery tar's original stock ELF digest in GitHub CI. Still no firmware build or flashing.

## Host CI

`tests/test_step141_readonly_firmware_preflight.py` checks flag acceptance/rejection, exact hardcoded stock ARM opcodes, in-memory-only patch-placement inspection, synthetic safe and malicious tar members, mismatch rejection, and absence of firmware upload or write operations. These tests use fake data; they cannot verify the developer's local `extracted/` inputs, the genuine recovery binary or the live Wi-Fi device.

## Gate status after Step 141

- **Static original input/structural integrity:** can be established by the user's local report, not by GitHub CI alone.
- **Full experimental patched/repaired ELF:** **not yet built or independently inspected**.
- **Dynamic loader imports and ABI in target process:** **not verified**.
- **Live combined-stream setup and media:** **not tested**.
- **Recovery from nonbooting/unreachable dongle:** **not independently proven**.

**Next gate, only after reviewing the local Step 141 report:** build in an isolated host/container output and validate the resulting patched ELF and `libSdH.so` symbols, relative branches, sections/segments, loader imports and tar member hashes. Preserve untouched stock and recovery artifacts. Do not flash on the strength of the offline static preflight alone.
