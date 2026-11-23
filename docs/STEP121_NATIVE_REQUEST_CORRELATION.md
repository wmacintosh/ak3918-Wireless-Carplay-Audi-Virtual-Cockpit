# Step 121 — Native request identity and orphaned-build blocker

**Status: source-only investigation, 2026-11-21. NOT safe for firmware packaging or flashing.**

## Established evidence

The verified stock `sdDongle` SHA-256 is
`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.

Existing Step 117–119 reports establish this order in the native outgoing SETUP path:

1. `0x2fadc` — array-ensure hook; the shim may replace the local stream array with one containing stream 111.
2. `0x2faec` — native code inserts that array into the outgoing request dictionary.
3. After `0x2fafc` — additional serialization/message-construction code can fail before the send call.
4. `0x2fbb0` — the native HTTP send call, replaced by `shim_screen_http_send` in experimental mode.
5. `0x2fe1c..0x2fe38` — stock cleanup releases local CF and HTTP message references.

The current shim stores a `combo_build` by `pthread_self()` and generation, **not** by native request/message identity. The send hook consults this per-thread record, and the request message pointer exists only by the later send call.

## Confirmed source-level hazard (not an observed device incident)

An injected request A may fail while serializing **before** it reaches the send hook. Its `combo_build` remains in use. A later stock-only request B on the **same thread** can then enter the send hook with the stock callback address. Since `combo_prepare_send_locked` only tests thread, generation and callback compatibility, it can claim request B using A's obsolete connection ID and install the response wrapper on B.

The added negative diagnostic in `tests/run_step120_host.py` constructs precisely this sequence using the **actual extracted C helpers**. It asserts that the current implementation makes the unsafe association, so a passing test **confirms the blocker**, not a safety guarantee. The diagnostic subsequently passed in GitHub Actions on 2026-11-21; this is a **reproduction of a source-level defect**, not device runtime validation.

This is independent of the teardown/send TOCTOU race: session finalization can still occur after the hook releases `g_state_lock` but before/during the native transport call.

## Read-only next step

On the Mac containing the verified stock ELF and Docker ARM toolchain, run from **your GitHub repository clone** (not necessarily from the stock diagnostics folder):

```bash
git fetch origin
git switch wip/ak3918-step115-callback-tombstones
AK3918_ROOT="$HOME/AK3918_Diagnostics" bash scripts/step121_extract_native_request.sh
python3 tests/run_step120_host.py
python3 tests/test_step122_paths.py
```

Set `AK3918_ROOT` to whichever folder actually contains `stock_analysis/sdDongle`. The extraction script verifies the stock binary SHA-256 before launching the Docker disassembler. Its new full native-function range `0x2f6b8..0x30310` fills the two gaps in the original Step 121 extraction. The script now generates two local files automatically:

- `~/Desktop/AK3918_step121_native_request_lifecycle.txt` — raw read-only ARM disassembly.
- `~/Desktop/AK3918_step121_native_request_lifecycle_paths.md` — Step 122 *candidate* branch/exit inventory, produced by `scripts/step122_native_request_paths.py`.

Neither script modifies, packages, or installs firmware. A static candidate exit cannot prove a bug occurs at runtime, and even an apparently complete path map cannot establish request ownership, concurrency or safety.

Inspect this disassembly to determine:

- Whether `0x2fafc` is a serialization call, what its success/failure branches are, and all exits that bypass `0x2fbb0`.
- Which *one native request identity* is available at both array publication and send, including intermediate dictionary/message pointers and stack locals.
- Whether native code can reenter these hooks on the same thread.
- The exact message ownership and error cleanup semantics if a request is deliberately rejected.
- Native send locking, callback/reentrancy and session finalizer ordering needed to close the teardown-to-send race.

## Design gate before another source change

Do not infer that a `pthread_t`, session generation, callback pointer or even an HTTP message address alone identifies the outgoing request *at both hook sites*. Only introduce a new correlation/cleanup hook after matching its exact ARM callsites and all error exits in this stock binary.

If the early-failure path cannot be identified and cleaned up reliably, preserve the fail-closed default `AK_ENABLE_COMBINED_CLUSTER=0` and keep the experiment unflashable. Preserve the original recovery archive. Host syntax/sanitizer success cannot establish target ABI or runtime safety.
