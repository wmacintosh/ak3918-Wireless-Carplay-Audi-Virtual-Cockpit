# Step 129 — Release status, archive policy and remaining validation

**Branch:** `wip/ak3918-step115-callback-tombstones`. **Status:** experimental, no independently verified on-dongle test of this revision. **Do not treat a green GitHub Actions run or an ARM/uClibc ELF inspection as permission to flash.**

## Distinct firmware generations

| Artifact / branch | What it represents | Deployment status |
| --- | --- | --- |
| `main` and `ak3918-ready-to-flash.zip` | Historical installer and firmware package described as tested by the repository author on their 2018 A5 / MHI2Q P5087 | An older **different build**; the README's historical statement must not be used as validation of WIP code |
| `stock_ak_202610081659.tar` | Original AK3918AN/Suding firmware recovery archive | Keep byte-for-byte unchanged and independently verify checksum/target compatibility before relying on it |
| Current WIP `altscreen.c`, `build_hook.py` | OMKE-inspired AK3918 ARM adaptation with stream 110/111 correlation, teardown admission and callback guards | Host-tested experimental source. **Not vehicle validated** |
| `ak_hook_step128_test.tar` | Combined stream-111 opt-in archive, with a distinct file name | **Only** generated on explicit opt-in. Experimental/unvalidated; not an automatic release or an authorized on-dongle flash |
| Legacy `ak_hook.tar` | Legacy package filename used by older builds | Never permit combined 111 content via the legacy flag |

## Packaging safety matrix

`build_hook.package_plan()` runs **before filesystem writes** and is tested independently of cross-compiler availability.

| `AK_ENABLE_COMBINED_CLUSTER` | `AK_STEP100_ALLOW_UNVERIFIED_PACKAGE` | `AK_STEP128_ALLOW_TEST_PACKAGE` | Result |
| --- | --- | --- | --- |
| 0 | 0 | 0 | No archive |
| 1 | 0 | 0 | No archive |
| 0 | 1 | 0 | Historical `ak_hook.tar` |
| 1 | 1 | 0 or 1 | **Rejected** before build |
| 0 | 0 | 1 | **Rejected** before build |
| 1 | 0 | 1 | Explicit `ak_hook_step128_test.tar` (unvalidated; never overwritten onto historical archive) |

Passing this policy does **not** authorize flashing. The test archive contains executable firmware and can be dangerous if manually installed.

## Step 129 source and test changes

- Combined-mode `shim_screen_http_send` now releases request tracking **only when native send was definitely not called** (e.g., a missing HTTP client). It does not install its response callback or increment an outstanding-send counter in that path.
- **Steps 131–133:** Verified-stock ARM disassembly proves nonzero `http_send` return is a pre-retain/pre-dispatch preparation error and its ticket can be reclaimed. **Step 133 corrected the meaning of zero:** the void async dispatcher can fail a 12-byte work-node allocation, leaving no queued callback even though `http_send` returns zero. All zero-return tickets therefore remain fail-closed until a matching callback; see [Step 131](STEP131_NATIVE_HTTP_FAILURE_RETURN.md) and [Step 133](STEP133_QUEUE_OWNERSHIP_AND_FINAL_RELEASE.md).
- The Step 129 integration harness compiles actual `shim_screen_http_send` and `shim_session_teardown` bodies extracted from `altscreen.c`, with controlled pthreads and stock transport stubs; this complements the existing isolated Step 128 helper test. No real HTTP or receiver-session hardware execution occurs.
- CI includes all four host C syntax combinations of `AK_ENABLE_COMBINED_CLUSTER={0,1}` and `AK_ENABLE_PHONE_CMDS={0,1}`. **The user separately ran the four-mode ARM/uClibc matrix on their Mac and reported PASS for every combination (November 21, 2026).** GitHub Actions still performs only host syntax checks for these modes; the local ARM result is not a device-runtime test.
- The old Step 125 race regression is explicitly a *negative control for the previous implementation*, not proof that Step 128/129 has the same race.

## Branch integration audit

- `fix/ak3918-lifecycle-repair-20261120` is an ancestor of the current WIP branch (WIP is ahead, not diverged). Do not cherry-pick it again.
- `fix/ak3918-session-lifecycle-audit-20261119` is **diverged** from WIP. Its older audit documentation identifies vendor phone-session ownership gaps; comparison does not demonstrate that every speculative fix on that branch should be merged.
- Draft PR #1 targets older `fix/ak3918-sigsegv-guards-20261119` and does not represent the latest WIP integration.

Avoid merging another branch wholesale until all changes are reviewed against the current wrapper and stock ARM evidence.

## Reproducible ARM/uClibc matrix — all four local configurations passed

The **local Mac Docker** script `scripts/step129_validate_arm_matrix.sh` builds and validates all four ARM926EJ-S/uClibc shared-library configurations in a disposable temporary directory. Both the repository source and Buildroot volume are mounted read-only; it never patches `sdDongle` or creates a firmware archive. The user supplied terminal output for a successful run after fast-forwarding to commit `62d34c6f80f65690e9ae44a8ff1bd3e86e31a56f`, with `PASS` for combined=0/phone=0, combined=0/phone=1, combined=1/phone=0, and combined=1/phone=1. The script also reported that it did not modify firmware/recovery binaries or tar archives. **This records user-reported local validation, not an independently collected build log or a GitHub-hosted ARM matrix run.**

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step129_validate_arm_matrix.sh
```

A passing result validates compilation, ARM/soft-float identity, `libc.so.0`, `libSdH.so` SONAME, constructor, and exported hooks. It is **not an integration or device-runtime test**.

## Step 130 session-switch gate — updated ARM matrix passed

The experimental branch includes [Step 130's old-session phone-command drain](STEP130_SESSION_REPLACEMENT_GATE.md). After pulling the Step 130 source commit `6d14d60`, the user reran `scripts/step129_validate_arm_matrix.sh` on their Mac and reported **PASS** for all four `AK_ENABLE_COMBINED_CLUSTER` / `AK_ENABLE_PHONE_CMDS` configurations. This supersedes the earlier pre-Step-130 local result for source compilation, but is not validation of a flashed firmware image or device-runtime behavior. The native phone-command dispatcher can still hang; the new wait preserves lifetime at the cost of potentially blocking replacement if it does not return.

## Before any device installation

1. Four ARM/uClibc combinations have passed the local source-only compiler/ELF matrix (user-reported). **Still required before device testing:** independently inspect final patched ELF, all applied hook callsites, import resolution and target-device ABI; the matrix does not patch the stock executable.
2. **Completed in Steps 131–136:** verified-stock ARM nonzero HTTP send return bypasses dispatch and both retains, so its ticket is reclaimed. The HTTP client separately retains its queue (`0xa64a8`) and its CF finalizer releases that reference (`0xa4b1c`), while successfully inserted queue work has an independent reference through its dispatch callback. **Still unresolved:** a zero-return dispatch attempt can fail to allocate its work node, leaving native retains and shim tickets without a completion. No timeout-based or finalizer-based ticket reclaim is authorized. See [Step 136](STEP136_HTTP_FINALIZER_CONTROL_FLOW.md) and the [Step 137 missing-callback ambiguity audit](STEP137_UNOBSERVABLE_DISPATCH_FAILURE.md), including an explicit source-derived premature-reclamation negative control.
3. Extend host testing to true native session setup/callback sequences (including nested reentrancy and reconnects), then collect actual device logs with the untouched stock recovery package confirmed.
4. Reconcile the **public `main` README** separately before promoting experimental content into a release; it currently describes a historical tested package, not this branch.
5. Do not flash the Step 128/129 experiment solely because these source checks pass.

## Step 140 source-level stream-111 compatibility — host only

[Step 140](STEP140_STREAM111_SOURCE_COMPATIBILITY.md) adds a source-derived C host test for original stream 110 plus experimental stream 111, the correlated send/response callback, stale-session gating and port validation. It also verifies by C preprocessing and Python AST that the two experimental screen hooks at `0x2fadc` and `0x2fbb0` are installed only under the combined flag. The tests are not evidence of a functional Audi Virtual Cockpit media stream, correct native plist serialization, or runtime-safe target integration. Experimental packaging, deployment and unverified firmware flashing remain disallowed.

## Step 141 offline pre-flash input and recovery integrity gate — no build

The source-only [Step 141 pre-flash gate](STEP141_EXPERIMENTAL_PRE_FLASH_GATE.md) adds a **read-only** Mac-side script that checks the builder's exact original `extracted/sdDongle` SHA-256 and known ARM callsites; checks proposed trampoline placement **in memory only**; checks the historical stock recovery tar hash and matching original library members; and refuses unclean WIP trees, wrong build flags or the legacy package mode. Host CI covers negative-control fixtures only; a successful CI result does not prove that the user's local inputs pass.

The script's result is **not** a flash authorization. Before any experimental installation, the repaired/patched ELF, loader ABI/import resolution and target recovery method independent of booted Wi-Fi/HTTP CGI must be reviewed. The historical `flash_ak.py` selects `ak_hook.tar` or `--stock`, not `ak_hook_step128_test.tar`; do not rename experimental firmware to bypass that separation.

## Step 142 isolated patched-ELF validation — completed on Mac

The actual user-run [Step 142 isolated build and static audit](STEP142_ISOLATED_PATCHED_ELF_AUDIT.md) **passed** for both feature flags enabled. The original stock hash, all four correct ARM trampolines, callback pointer slots, five original display patches, new ELF dynamic string table, `DT_NEEDED=libSdH.so`, `RUNPATH=$ORIGIN`, uClibc/ARM soft-float shared-object metadata and expected exports were verified on the disposable built bytes. See [archived full user-pasted report](../evidence/AK3918_step142_isolated_elf_audit_uploaded.md).

This clears the **static build and ELF-layout** gate, **not** the target loader/runtime or unbrick recovery gate. The temporary experiment was deleted; no flashable archive was built. Undefined dynamic symbol resolution against the target's actual libraries, native callback lifetime and independent recovery if the network/CGI goes away are still unverified. Do not substitute old `ak_hook.tar` or rename an experimental test archive to use the historical flashing tool.

## Step 143 — Loader symbol inventory PASS on Mac; physical recovery still blocked

[Step 143](STEP143_LOADER_RECOVERY_CHECK.md) adds a **separate** read-only ELF dynamic-import/provider audit and recovery-route classification. It distinguishes verified-stock `sdDongle` and the four original vendor libraries from the Buildroot toolchain's libc/pthread candidates, rather than treating the development sysroot as the installed dongle's runtime. The experimental `libSdH.so` was compiled **ephemerally** with both feature flags enabled. The [complete user-provided Step 143 report](../evidence/AK3918_step143_loader_recovery_audit.txt) passed, with **33/33 strong dynamic imports accounted for** and none unknown within the provided provider set. All 33 strong imports, including pthread symbols, resolved by name to the **development toolchain's** `libc.so.0` (SHA-256 `42891edc20c0f47833248f0dc312199e051e966e2a9b0e859f0137ebe55603d7`). That library is **not verified as identical to the dongle's installed libc**, so this is not device-loader validation.

The existing `flash_ak.py --check-only` **still uploads archive chunks**, despite skipping submission and reboot. Do not treat it as a harmless read-only device check. Both historical update and `--stock` restore remain dependent on the dongle booting to serve CGI, which is not a verified recovery route for a nonbooting unit. No specific hardware bootloader/UART recovery path is documented as working on this board revision.

Static import coverage cannot prove correct **target** loader/linker resolution, exact installed uClibc symbols, or runtime safety. Experimental packaging and flashing remain blocked.

## Step 144 — Explicit read-only live device fingerprint (awaiting Mac run)

[Step 144](STEP144_TARGET_IDENTITY_AND_RECOVERY_EVIDENCE.md) adds a **single GET, explicit-opt-in** collector for the known stock Suding `/cgi-bin/getversion.cgi` endpoint at `192.168.200.1`; it refuses redirects, unknown devices and oversized responses and redacts non-allowlisted fields. The default invocation makes **no network requests**, and GitHub CI only tests mocked HTTP responses. No authenticated shell, firmware CGI upload, command injection, reboot, filesystem reads or persistent target-side action is performed.

Even a successful target identity GET **cannot** establish the installed `libc.so.0` / `ld-uClibc.so.0` hashes or a verified board-specific unbrick mechanism. Research on different AK3918-based adapters is not evidence for this specific unit's recovery layout. Experimental packaging/flashing remains blocked.

**No existing firmware files, device configuration, recovery tar, or `main` contents were modified by Steps 129–144.**
