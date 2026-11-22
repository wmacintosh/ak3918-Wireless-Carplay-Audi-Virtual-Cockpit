# Step 142 — Isolated ARM/uClibc patched-ELF and loader-metadata audit

**Status:** test and report collection prepared. Mac execution and actual patched-ELF output are pending. **Not an approval to package, upload or flash firmware.** No production C code, patcher, original stock binary, recovery archive, historical firmware or `main` was changed.

## Basis

The user-provided Step 141 Mac preflight at commit `3273d0057bba` passed exact stock SHA-256, three original hook instruction words, five historical display patch sites, distinct four in-memory mapped trampoline candidates, recovery tar integrity and equality of all five builder inputs to the original stock tar. It selected `AK_ENABLE_COMBINED_CLUSTER=1` and `AK_ENABLE_PHONE_CMDS=1`, and reported `AK_UCLIBC_CC` unset in the host shell. This is expected: use the existing Docker-contained ARM926EJ-S/uClibc toolchain.

Step 141 validated **only the inputs**. The patched executable has not yet been built or examined. Step 142 closes this specific static gap *without creating a flashable file*.

## Safe execution model

Run `scripts/step142_isolated_elf_audit.sh`. The wrapper first reruns the Step 141 input gate. It then starts the existing `ak3918-buildroot:latest` ARM64 Docker image with:

- `--network none`, `--pull never` — it cannot contact the dongle, download dependencies, or reach a live Wi-Fi device.
- A read-only bind for the GitHub repository and read-only Buildroot toolchain volume.
- **No persistent host output mount for ARM executables or patched firmware.** Only a text log is captured to the Mac.
- A disposable Docker working directory removed on exit. The original `sdDongle`, four stock libs, `altscreen.c`, `build_hook.py` and `repair_elf.py` are copied inside the container; no repository files are modified.
- Both requested feature flags enabled for the ARM compile, with both packaging flags disabled; it **does not invoke** `build_hook.main`, `make_tar`, `flash_ak.py` or any device CGI endpoint.
- Separate explicit calls to `build_hook.build_shim`, `build_hook.patch_sddongle`, and `repair_elf.repair` operate **only on ephemeral container copies**.

The isolated build intentionally creates a short-lived, modified `sdDongle` and `libSdH.so` **within Docker** solely for static inspection. Neither executable persists outside that container; no archive is created. The report is text-only and may be shared.

## Exact audit coverage

`scripts/step142_audit_patched_elf.py` checks the freshly built bytes, rather than relying on build logs alone:

| Audit | Required proof |
| --- | --- |
| Original identity | Pre- and post-copy original ELF has pinned SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1` |
| Patch callsites | `0x05ec50` setup, `0x02fadc` stream array and `0x02fbb0` HTTP send have ARM-state BL instructions whose signed targets resolve to 12-byte executable trampolines |
| Trampoline pointers | Verified ARM words `e59fc000`, `e59cf000`, and the original expected callback slot addresses `0x1369fc`, `0x13c644`, `0x13c648` |
| Session class callback | `AirPlayReceiverSession.finalize` slot at `0x134078` now targets a *different* trampoline whose final word is `0x13c640` |
| Five altScreen changes | Patched ARM instruction words match exactly the expected replacements |
| BSS reservation | `.bss` grows by 12 bytes, allocating three 32-bit callback slots for combined mode |
| ELF repair | Patched image grows by the expected 64 KiB aligned insertion; relocated `.dynstr` preserves the original dynamic strings and adds only `libSdH.so` and `$ORIGIN` |
| Dynamic-loader metadata | `DT_STRTAB`, `DT_STRSZ`, exactly one new `DT_NEEDED=libSdH.so`, and `DT_RUNPATH=$ORIGIN` are internally consistent |
| PT_LOAD mapping | Exactly two segments remain aligned, correctly bounded and nonoverlapping |
| ARM shared library | `libSdH.so` is a 32-bit ARM shared object, declares `libc.so.0`, its SONAME, constructor, and all required shim exports |

The cross-compiled `readelf` output also archives dynamic tags, relocations, segment mapping and undefined symbols for deeper review. **A static success is not evidence** that the vendor loader resolves every dependency at runtime, the native callback ABI behaves correctly under concurrency, packets reach the Virtual Cockpit, or a nonbooting device can be restored.

## Run on Mac

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
set -o pipefail
bash scripts/step142_isolated_elf_audit.sh \
  | tee "$HOME/Desktop/AK3918_step142_terminal.txt"
```

The script itself writes the complete report to `~/Desktop/AK3918_step142_isolated_elf_audit.txt`, including any failed build/validation output. The second `tee` file is optional and contains the same streamed terminal log. If a Docker/ARM error occurs, the command exits nonzero and must not be bypassed. **Do not add test-package flags, call `build_hook.py` directly, or invoke `flash_ak.py` as a response to a failed audit.**

## CI and limitations

`tests/test_step142_isolated_elf_audit.py` pins the no-flash/no-network/no-output-mount shell isolation, source constants, ARM BL target decoding, malformed ELF rejection and static audit requirements. GitHub CI does not have the user's Buildroot Docker volume; therefore a green CI run validates only source/shell/host test logic, **not the actual patched ELF**.

**Next:** review the actual Mac report, check any mismatch or undefined/import relocation, and independently establish an out-of-band recovery method if the dongle cannot boot or serve CGI. Neither Step 141 nor Step 142 clears the live flash gate. The historical `flash_ak.py` continues to target the older `ak_hook.tar` and must not be repurposed by renaming a test archive.
