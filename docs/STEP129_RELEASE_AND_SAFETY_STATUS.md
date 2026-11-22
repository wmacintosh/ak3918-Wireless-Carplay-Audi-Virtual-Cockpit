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
2. **Completed in Step 131:** verified-stock ARM nonzero return bypasses enqueue and both retains; its ticket is reclaimed. Local exact-opcode verification and all four ARM/uClibc configurations passed at `263596b`. **Still unresolved:** safely handling any zero-return dispatch attempt without a callback, including actual queued requests and native node-allocation failure. No timeout-based ticket reclaim is authorized.
3. Extend host testing to true native session setup/callback sequences (including nested reentrancy and reconnects), then collect actual device logs with the untouched stock recovery package confirmed.
4. Reconcile the **public `main` README** separately before promoting experimental content into a release; it currently describes a historical tested package, not this branch.
5. Do not flash the Step 128/129 experiment solely because these source checks pass.

**No existing firmware files, device configuration, recovery tar, or `main` contents were modified by Step 129.**
