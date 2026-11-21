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

The added negative diagnostic in `tests/run_step120_host.py` constructs precisely this sequence using the **actual extracted C helpers**. It asserts that the current implementation makes the unsafe association, so a passing test **confirms the blocker**, not a safety guarantee. The modified test has not yet been executed in a compiler in this GitHub-only update.

This is independent of the teardown/send TOCTOU race: session finalization can still occur after the hook releases `g_state_lock` but before/during the native transport call.

## Read-only next step

On the Mac containing the verified stock ELF and Docker ARM toolchain:

```bash
cd ~/AK3918/01_Development/AK3918_Diagnostics/ak3918-sigsegv-fix
git fetch origin
git switch wip/ak3918-step115-callback-tombstones
bash scripts/step121_extract_native_request.sh
python3 tests/run_step120_host.py
```

The script produces `~/Desktop/AK3918_step121_native_request_lifecycle.txt` without modifying or installing firmware.

Inspect this disassembly to determine:

- Whether `0x2fafc` is a serialization call, what its success/failure branches are, and all exits that bypass `0x2fbb0`.
- Which *one native request identity* is available at both array publication and send, including intermediate dictionary/message pointers and stack locals.
- Whether native code can reenter these hooks on the same thread.
- The exact message ownership and error cleanup semantics if a request is deliberately rejected.
- Native send locking, callback/reentrancy and session finalizer ordering needed to close the teardown-to-send race.

## Design gate before another source change

Do not infer that a `pthread_t`, session generation, callback pointer or even an HTTP message address alone identifies the outgoing request *at both hook sites*. Only introduce a new correlation/cleanup hook after matching its exact ARM callsites and all error exits in this stock binary.

If the early-failure path cannot be identified and cleaned up reliably, preserve the fail-closed default `AK_ENABLE_COMBINED_CLUSTER=0` and keep the experiment unflashable. Preserve the original recovery archive. Host syntax/sanitizer success cannot establish target ABI or runtime safety.
