# Step 127 — Native HTTP queued dispatch target

**Status: read-only static analysis; no combined-mode flashing or packaging permitted.**

## Source evidence

Step 126 uploaded ARM objdump from the verified stock `sdDongle` (SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`) proves:

1. `0x82c74` branches to `0x85b50`, the typed CoreFoundation retain wrapper. The ordinary mutable CF-object path calls `0xf0090` with `+1` at `0x85bdc`. `0x82c78` branches to `0x85c04`, which calls `0xf0090` with `-1` at `0x85c90` and destructs/frees the object when the count reaches zero.
2. `http_send` retains the message (`0xa6a4c`) and HTTP client (`0xa6a54`), puts client in `msg+0x8ec`, and queues the message with `0xa1900` (`0xa6a6c`). This establishes **retain calls before queue insertion**, not balanced release or retention of the receiver session.
3. The queue insertion helper at `0xa1900` allocates a 12-byte node, stores the message and callback pointer, locks `queue+0x2c`, adds the node, may notify an indirect function (`0xa1a3c`) under that mutex, and then unlocks.
4. The nearby function at `0xa1b74` opens, binds, and connects a socket; it is **not** a queue drain. It can itself enqueue work with `0xa1900` (`0xa1df4`).
5. The stock response completion helper `0xa1338` increments a condition counter and signals a condition variable under its own lock.
6. The native receiver finalizer calls a function pointer at `session+0x20` (`0x66a94`), tears down resources, destroys `session+0x80` mutex (`0x66b34`), and releases a CF object at `session+0x0c` (`0x66ba8`). The existence of the queue retain calls does not prove this session is held alive.

## Precise callback registered with queue

At the stock send entry:

- `0xa6a58`: load PC-relative word from literal at `0xa6a94`, which is `0xfffff5d8` (signed `-0xa28`).
- `0xa6a60`: `add r2, pc, r2`. ARM state PC reads as the instruction address plus 8 (`0xa6a68`), so `r2 = 0xa6a68 - 0xa28 = 0xa6040`.
- `0xa6a6c`: `bl 0xa1900` with `r1=message` and `r2=0xa6040`.

`0xa6040` is the **exact queued dispatch callback pointer value** for this verified stock binary. Step 127 disassembly now confirms it links the message into the client's pending list, calls `0xa53fc(client)` to start processing, and releases **the client** through `0x82c78`. It does **not** establish release of the separately retained message or final network completion. The callback pointer `0xa6040` is distinct from the indirect global notifier invoked at `0xa1a3c` under the queue mutex. See [Step 128](STEP128_HTTP_PROCESSOR_AND_RELEASE_AUDIT.md) for the evidence and next trace.

## Step 127 read-only extraction

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step127_extract_queue_completion.sh
```

Output: `~/Desktop/AK3918_step127_queue_completion.txt`.

The script checks the exact stock SHA-256, uses read-only Docker mounts and temp-file publication, and captures:

- `0xa5e80..0xa6320` — `0xa6040` queued completion callback and surrounding calls;
- `0xa14a0..0xa18d8` — candidate native dequeue path preceding `0xa1900`;
- `0xa1900..0xa1b24` — enqueue, mutex and notifier;
- `0xa12c0..0xa13b8` — stock response completion signal;
- `0xa63d0..0xa6974` — HTTP message lifecycle neighbors;
- `0x66a80..0x66c1c` — finalizer.

These are audit **ranges**, not confirmed boundaries of routines. No firmware artifact is built or flashed.

## Deployment decision remains unchanged

Step 125's deterministic host test demonstrates that a combined send can pass the shim's generation check and start native send after another thread invalidates the session. The stock client's/message's reference management may prevent a particular use-after-free, but cannot establish the protocol or session teardown is safe.

**Do not hold the shim lock through stock send, wait indefinitely in finalizer, or assume a message callback pins receiver-session state until the queue-drain/response path is verified.** `AK_ENABLE_COMBINED_CLUSTER` remains 0 by default; the unverified combined build/package veto stays in force.

## Review result (2026-11-21)

Step 127 has been completed using the user's attached read-only disassembly. The callback at `0xa6040` is **not** the terminal HTTP response callback; it appends the message and dispatches client processing via `0xa53fc`, then releases the client's send-retained CF reference. Step 128 tracks the still-unverified message release and teardown behavior. The existing combined-mode package veto remains in place.
