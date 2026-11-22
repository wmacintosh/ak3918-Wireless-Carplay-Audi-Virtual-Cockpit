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
- Native `http_send` returning nonzero remains ambiguous until every error/enqueue path is proven. Its ticket stays canceled until a callback is seen. This is intentional fail-closed logic, but repeated opaque failures can still fill the eight-slot table: **not resolved in full**.
- The Step 129 integration harness compiles actual `shim_screen_http_send` and `shim_session_teardown` bodies extracted from `altscreen.c`, with controlled pthreads and stock transport stubs; this complements the existing isolated Step 128 helper test. No real HTTP or receiver-session hardware execution occurs.
- CI includes all four C syntax combinations of `AK_ENABLE_COMBINED_CLUSTER={0,1}` and `AK_ENABLE_PHONE_CMDS={0,1}`. **Only the host syntax combinations are run in CI**; previous ARM/uClibc validation reports did not cover every combination, and those builds require repeating on the verified local toolchain.
- The old Step 125 race regression is explicitly a *negative control for the previous implementation*, not proof that Step 128/129 has the same race.

## Branch integration audit

- `fix/ak3918-lifecycle-repair-20261120` is an ancestor of the current WIP branch (WIP is ahead, not diverged). Do not cherry-pick it again.
- `fix/ak3918-session-lifecycle-audit-20261119` is **diverged** from WIP. Its older audit documentation identifies vendor phone-session ownership gaps; comparison does not demonstrate that every speculative fix on that branch should be merged.
- Draft PR #1 targets older `fix/ak3918-sigsegv-guards-20261119` and does not represent the latest WIP integration.

Avoid merging another branch wholesale until all changes are reviewed against the current wrapper and stock ARM evidence.

## Before any device installation

1. Independently reproduce ARM/uClibc cross-build for the chosen feature flag combination and inspect ELF dynamic imports, hook callsites and target architecture.
2. Review queue error paths and verify that a nonzero return cannot enqueue a callback before deciding to reclaim its ticket.
3. Extend host testing to true native session setup/callback sequences (including nested reentrancy and reconnects), then collect actual device logs with the untouched stock recovery package confirmed.
4. Reconcile the **public `main` README** separately before promoting experimental content into a release; it currently describes a historical tested package, not this branch.
5. Do not flash the Step 128/129 experiment solely because these source checks pass.

**No existing firmware files, device configuration, recovery tar, or `main` contents were modified by Step 129.**
