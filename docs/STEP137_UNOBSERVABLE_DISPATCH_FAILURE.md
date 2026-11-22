# Step 137 — Missing callbacks: undetectable native dispatch-node allocation failure

**Status:** verified-stock static control flow reviewed; deterministic host negative controls added. No new firmware source patch, target image, recovery changes, `main` edits, package or flash. This step uses [Step 133's archived stock disassembly](../evidence/AK3918_step133_queue_ownership.txt) plus [Step 136's verified HTTPClient finalizer](../evidence/AK3918_step136_http_finalizer.txt); a new Mac extraction is not required.

## The actual failure

In the exact stock AK3918AN `sdDongle` (SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`), the native wrapper `HTTPClientSendMessage` at `0xa6974` makes three distinct decisions:

| Native condition | Verified ARM path | Return visible to shim | Can shim safely free the ticket? |
| --- | --- | --- | --- |
| HTTP preparation returns nonzero | `0xa69c0` stores error, `0xa69c4` bypasses two retains and dispatch, `0xa6a00` branches to return | Nonzero | **Yes**, exact ticket only: no native enqueue, no callback expected |
| Native dispatch successfully allocates its node | `0xa6a4c` message retain, `0xa6a54` client retain, `0xa6a6c` calls `0xa1900`; `calloc` at `0xa1980` succeeds, branch `0xa1988 → 0xa19cc`, node linked `0xa19f4` | **Zero** at `0xa6a70` | **No**, a callback may arrive after teardown or timeout |
| Native dispatch fails allocating its 12-byte node | Same two retains and same `0xa6a6c` call; `calloc` at `0xa1980` returns null; diagnostic `0xa19c0`, return `0xa19c8` **before node insertion** | **Also zero** at `0xa6a70` | **No**, because the shim cannot distinguish this from the preceding successful insertion |

Other invalid-queue cases may likewise return without insertion. The dispatch function does **not return a failure code to its HTTP caller**, and the HTTP wrapper sets `r5=0` after the attempt. Native retains taken before the dispatch call are not balanced by the dropped work node. This is a **potential native retained-object leak if the allocator or validation failure occurs**; it is not proven to have happened on the user's physical dongle.

The normal `HTTPClient` CF finalizer `0xa4b08` releases its client-held queue reference at `0xa4b1c`; its finalization does **not** invoke the message completion callback and cannot be assumed to run when a native client retain is stranded. The normal dispatch worker releases a separate work-held queue reference at `0xa30a4` after executing its callback. Neither path supplies the missing synchronous success/failure signal.

## What cannot be inferred from the exposed interface

A zero-return send leaves two observationally equivalent possibilities at the shim boundary:

- **Pending native work** — callback is queued; a late callback could receive a reused `message` address after a reconnect.
- **Dropped work** — no callback can arrive *from that insertion attempt*; its shim metadata could remain forever.

The shim has no justified test that distinguishes these at the moment of return. Native queue backlog size, a deadline, HTTP client invalidation or CF finalization does not constitute a proven per-message cancellation acknowledgment. Thus no purely timeout-, reconnection- or return-code-based metadata reclamation is safe. This does not prove that **every conceivable invasive native instrumentation method** is impossible; it describes the limits of the current API and verified stock paths.

## Step 137 regression coverage

`tests/test_step137_dispatch_ambiguity.py` pins the exact original ARM opcodes for the two retains, the allocation/null branch, drop-path return, success-only insertion and forced zero HTTP return. It also checks that production shim cancellation does not clear accepted request metadata and that Step 136's finalizer cannot substitute for HTTP message completion. Mutation tests reject opcode drift.

`tests/run_step137_accepted_send_ambiguity.py` compiles **the real C request-tracking and send-admission helpers extracted from `altscreen.c`**, not invented replacements. It runs native-boundary models as normal and UBSan host binaries:

1. For **queued-but-delayed** and **allocation-dropped** attempts, the shim sees the same `rc==0` and has identical request records.
2. Eight zero-return attempts with no callback saturate the limited tracking table; teardown and reconnect do not erase those records; a ninth combined request is rejected.
3. A late callback for an old, canceled session consumes only the old record, and cannot start the next session; subsequent genuine callbacks free their own tickets.
4. A deliberately unsafe **negative control** simulates reclaiming a zero-return ticket before its callback. A later callback for the old message can then be misidentified as a *new* request at the same address and consume the new ticket. **This simulated premature reclamation is never performed by the production shim.**
5. Nonzero native *pre-dispatch* errors still reclaim exactly their tickets, consistent with Step 131.

These are host tests of source helpers and an **abstract model of the already-verified native alternatives**, not a live ARM allocator fault injection or evidence that the physical device has run out of memory.

## Decision and boundaries

**Keep `altscreen.c` unchanged for now.** Current fail-closed behavior is conservative and preserves the key safety invariant: after a zero-return native dispatch attempt, the ticket is reclaimed only on a matching callback. If eight records are stranded, new combined requests remain disabled rather than risking a stale callback changing the next session. Original stock recovery and historical firmware stay untouched.

To safely recover capacity beyond this guard would require a *separately validated* source of per-message truth, such as an observed enqueue success/failure notification with clear native retain balancing, or a proven cancellation barrier that prevents every future use of that message pointer. Replacing or instrumenting stock `dispatch_async_f`, changing its allocation semantics, releasing foreign CF objects manually or broad timeout clearing are not authorized by current evidence. Any proposed design must also handle allocation-failure leaks, callback concurrency and pointer reuse without risking stock transport.

**Step 138 completed the proposed source-only feasibility review:** [Enqueue acknowledgment feasibility and design contract](STEP138_ENQUEUE_ACK_FEASIBILITY.md). It rejects queue depth, timeouts, and log inference as per-request truth, and tests exact-ticket, retained-object rollback and callback-before-ack race conditions in a host-only model. No reliable **noninvasive** enqueue acknowledgment was identified. Green GitHub Actions results do **not** establish safety to package or flash the wireless Virtual Cockpit stream-111 experiment.
