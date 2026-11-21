# Step 119 — Confirmed stock CoreFoundation retain behaviour

## Source

Read-only disassembly in `AK3918_step119_retention_details.txt` from the original `sdDongle` firmware, whose known SHA-256 is:

`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`

## Array append implementation

- `0x82fc0` branches to `0x867a0`, which passes the element and jumps to `0x865b4`.
- At `0x86734..0x8674c` the real append implementation loads a callback from the array object at offset `0x0c` and calls it with the inserted element in `r1`.
- At `0x86750..0x8675c` it writes the element to the backing store and updates the count.
- The callback table at `0x134200` supplies the retain callback `0x85bfc` and release callback `0x85cf4`.
- In the same firmware, `0x85bfc` forwards the callback argument to `0x85b50`, and `0x85cf4` forwards to the reference-release implementation `0x85c04`.

**Interpretation:** Inserting a stream dictionary into a mutable array uses the installed retain callback, so the original stream 110 remains retained by the replacement array after the old array's local reference is released.

## Dictionary value insertion

- `0x836dc` forwards to `0x885f8`.
- At `0x88794..0x887a8` dictionary insertion loads the value callback at dictionary offset `0x24` and calls it with value argument `r9`.
- At `0x887d4..0x887e0` the original value pointer is saved into the new entry.
- The supplied dictionary value-callback table `0x1341d4` has the same retain/release callback pair (`0x85bfc` / `0x85cf4`).
- The stock outgoing SETUP function passes the constructed array to dictionary insertion and releases its local reference later (documented in Step 117).

**Interpretation:** Dictionary insertion independently retains the replacement array, matching the normal CoreFoundation reference-counting model.

## Decision

No additional correction to Step 112's `cf_release(replaced_streams)` is indicated. Its reference-counting pattern is consistent with the stock callsites and callback implementation. This is a *static binary verification*, not a proof of concurrency safety or runtime success.

## Distinct unresolved issue: teardown between array construction and HTTP submission

- `shim_screen_ensure_stream` injects stream type 111 at the native callsite `0x2fadc`.
- Stock code then inserts the array into the request dictionary at `0x2faec`, serializes/builds the HTTP message and calls the HTTP send function at `0x2fbb0`.
- `shim_screen_http_send` (Step 115) checks the session generation before installing the wrapper callback, but when no matching valid request exists it still calls `http_send(client,msg)` as the stock path.
- Therefore, teardown after array publication can cancel tracking while leaving an outgoing message that contains stream 111. The code cannot assume canceling the callback metadata cancels the wire request.
- Holding `g_state_lock` across stock CoreFoundation and HTTP calls would introduce unknown reentrancy/deadlock risks. Blocking finalization would also risk a permanent wait if native processing exits without reaching the send hook.
- Do **not** attempt to remove stream 111 from the message without first verifying how the stock HTTP message is serialized and owned; modifying its body in place could corrupt stock stream 110.

**Next action:** Determine an exact safe serialization-boundary gate or a proven lifetime handoff with balanced cleanup on every exit. Until then keep experimental combined-mode packaging disabled and do not flash.

## Scope of validation

Step 115 host sanitizer tests and target ARM *syntax checks* passed. The combined 111 build is not runtime verified. No firmware binary is modified or published by this document.
