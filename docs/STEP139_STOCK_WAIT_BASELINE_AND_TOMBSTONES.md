# Step 139 — Stock SETUP wait makes dropped async work a baseline failure

**Disposition: retain Step 115 as-is; reject invasive dispatcher instrumentation for this failure mode.** This is an evidence-only clarification, with no edit to `altscreen.c`, stock `sdDongle`, firmware recovery, package artifacts, or `main`.

## User-provided stock control flow

A previously supplied read-only ARM disassembly of the original `sdDongle` at `0x2f6b8` already contained the following code. The exact relevant instruction words, extracted and whitespace-normalized from that earlier user-provided report, are archived in [Step 139 stock wait excerpt](../evidence/AK3918_step139_stock_send_wait_excerpt.txt). This excerpt is **not** a fresh stock extraction and does not include the body of `0xa15b8`.

| Stock address | ARM code / effect | Interpretation |
| --- | --- | --- |
| `0x2fbb0` | `bl 0xa6974` | Call native `HTTPClientSendMessage(client,msg)` |
| `0x2fbb8` | `mov r4,r0` | Preserve native send return |
| `0x2fbf0` | `cmp r4,#0` | Test success |
| `0x2fbf4` | `beq 0x2fc20` | On **zero** result, reach wait path; nonzero takes error path toward `0x2fddc` via `0x2fc1c` |
| `0x2fc20..0x2fc44` | Timestamp and diagnostic output | This happens **before** waiting; the wait is not the instruction immediately after the send |
| `0x2fc48..0x2fc4c` | `mvn r3,#0; mvn r2,#0` | Registers `r2:r3` receive all-ones (`0xffffffffffffffff`), consistent with 64-bit `DISPATCH_TIME_FOREVER` |
| `0x2fc50` | `ldr r0,[r6,#0x30]` | Pass request-context synchronization object |
| **`0x2fc54`** | **`bl 0xa15b8`** | Call native semaphore/condition wait helper with no finite deadline evident at this callsite |
| `0x2ee68..0x2ee70` | Load `msg+0x8fc` context, then context `+0x30` | Stock HTTP response callback retrieves the matching synchronization object |
| **`0x2ee74`** | **`bl 0xa1338`** | Stock callback invokes the synchronization signal helper |

The [Step 128 audit](STEP128_DISASSEMBLY_AND_ADMISSION_GATE.md) already noted that the stock SETUP sender blocks on its local response synchronization object after successful `HTTPClientSendMessage`, and that `0x2ec7c` signals through `0xa1338`.

**Precision limit:** the instruction snippet shows the call to `0xa15b8` and the `-1/-1` arguments. It does not independently disassemble `0xa15b8` to prove all its internal wakeup, interruption or error branches. Nor does it exclude external process termination or other independent notifications. “Waits indefinitely if nothing signals” is a conditional control-flow risk, not an observed infinite hang on the device.

## Why the OOM path is a *stock* failure scenario

The existing, SHA-256-verified [Step 133 stock dispatch report](../evidence/AK3918_step133_queue_ownership.txt) establishes:

- `0xa6a4c` and `0xa6a54` retain message and client before the queue attempt.
- `0xa6a6c` invokes `dispatch_async_f(0xa1900)`.
- `0xa1980` attempts `calloc(1,12)` for the queue node. On null, control returns at `0xa19c8` without enqueuing `0xa6040`.
- `0xa6a70` still forces the HTTP sender's return value to zero.

Therefore **even with the unmodified stock binary and no Step 115 shim**, the send call can report success after a failed node allocation, sending the stock caller to its no-finite-timeout wait while leaving the corresponding completion work unscheduled. If nothing else signals that request's context, this thread can remain blocked indefinitely.

This is not proof that physical low-memory failure has occurred; it is a demonstrable **possible stock behavior**. Adding a shim timer, clearing tickets on reconnect, or patching native dispatch to mask an already-stock severe-OOM edge case is not justified by this evidence. It would risk a much more ordinary problem: a late response callback being misassociated with a future request after pointer reuse.

## Design decision

**Keep Step 115's eight-slot, callback-only tombstone design unchanged.**

- Native nonzero pre-dispatch failures can reclaim their exact ticket, as established in Step 131.
- After zero return, do not infer whether the node was queued. Preserve the ticket until its native callback arrives; cancel generation on teardown without erasing metadata.
- If eight callbacks never arrive, combined stream-111 requests remain fail-closed, rather than allowing stale callbacks to corrupt the next session.
- Do not add a dispatcher hook, explicit CF release, semaphore wakeup injection, queue-depth polling, or timeout reclamation to “fix” this case.
- Keep stock recovery, `main`, and all runtime firmware untouched.

A future target-runtime assessment would need independent evidence for genuinely *common* non-OOM lifetime failures; this theoretical severe-OOM edge case alone provides no reason to alter the vendor's synchronization semantics. Likewise, Step 138's hypothetical receipt contract remains research-only and is **not** a planned patch.

## Host-only regression test

`tests/test_step139_stock_wait_baseline.py` pins the exact user-provided stock send/wait/signal opcodes, independently pins the Step 133 native drop/return-zero path, and tests three abstract cases: a native pre-dispatch nonzero result skips waiting, a normally queued callback can signal and unblock, and a dropped dispatch node has no callback of its own while the stock caller has entered the wait path.

This is a simple **counterfactual model**, not an ARM runtime emulator, live semaphore test, or proof that no other signal exists. Existing Step 115/131/132/137 regression suites remain in force.

**Step 140 follow-up:** [source-derived 110/111 request-response and feature-flag compatibility checks](STEP140_STREAM111_SOURCE_COMPATIBILITY.md) have now been added. They exercise the unmodified C hook bodies with host CF/HTTP stubs and verify the extra screen-callsite hooks remain opt-in only. They do not validate car-side video transport or target runtime. No invasive dispatcher acknowledgment hooks are warranted without new, separately actionable evidence.
