# Step 126 — Stock HTTP ownership and dispatch audit

**Status (2026-11-21): static, read-only evidence. No firmware deployment.**

Input: user-supplied `AK3918_step125_native_http_transport.txt` (712 lines), disassembled from the SHA-256-verified AK3918AN stock `sdDongle`:

`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`

The code under test is the existing OMKE-based AK3918 ARM port on `wip/ak3918-step115-callback-tombstones`, not OMKE's MIPS AX1800M firmware.

## Confirmed from Step 125 ARM instructions

### Stock HTTP send: `0xa6974..0xa6a7c`

- `0xa6a08..0xa6a3c`: initializes per-message send/buffer pointers, including `msg+0x8bc`, `+0x8c0`, `+0x8c4`, `+0x8c8`, `+0x8cc`, `+0x8d0`.
- `0xa6a4c`: calls `0x82c74` with `r0=msg`; `0xa6a54`: calls the **same** function with `r0=client`. `0x82c74` is adjacent to the independently observed release helper `0x82c78`; it is a **candidate retain/reference increment**, not confirmed without its body.
- `0xa6a5c`: stores the client pointer into `msg+0x8ec`.
- `0xa6a68..0xa6a6c`: takes `*(client+8)` as queue-object input `r0`, passes the message as `r1`, passes a static function/data pointer as `r2`, and calls `0xa1900`. The stock send returns through `0xa6a74..0xa6a7c`.

**Implication:** The native send has an explicit reference-management and queue handoff boundary. The message/client are likely pinned across enqueue, but this remains a hypothesis until `0x82c74` and the queue consumer/release path are audited. Even confirmed message/client retention would **not**, by itself, prove receiver-session lifetime safety.

### Native transport queue: `0xa1900..0xa1b20`

- `0xa1978..0xa19d0`: allocates a 12-byte node with `calloc(1,12)`; saves the incoming message in node offset `+8` and incoming secondary argument in `+4`.
- `0xa19d4..0xa19d8`: locks a native mutex stored at queue-object offset `+0x2c`.
- `0xa19f0..0xa19fc`: appends the node to the queue's linked-list tail (`queue+0x34` and the previous tail).
- `0xa1a18`: signals a condition variable in a special queue state.
- `0xa1a20`: calls `0xa18d8`, a helper that in turn calls `0x8f564` and `0x8f078`.
- `0xa1a34..0xa1a3c`: if a process-level indirect callback is installed, invokes it through `blx r3` with `r0=0`, **before releasing the native queue mutex**.
- `0xa1b14..0xa1b20`: exits by calling `pthread_mutex_unlock` on the same mutex.

**Implication:** Blindly holding the shim's `g_state_lock` throughout `http_send` would create a possible lock-order/reentrancy hazard. The indirect callback takes `r0=0`, so it is **not demonstrated to be** the direct `shim_screen_response(msg)` callback; it may merely wake the queue. Its target and the queue consumer are unknown.

### Native stock response: `0x2ec7c..0x2ee8c`

- `0x2ec7c`: reads `msg+0x4a0` (response body length); `0x2ecac`: reads `msg+0x49c` (response bytes) and parses the plist.
- `0x2edcc`: compares descriptor type against stock stream **110**.
- `0x2ee68`: reads `msg+0x8fc` as stock screen context; `0x2ee6c`: writes returned data port to context offset `+4`; `0x2ee74`: calls `0xa1338` on context field `+0x30` (signal-like callback; precise semantics to check).
- The combined shim must keep calling this stock callback for 110 after its own 111 extraction; it does so today. A late callback runs stock but cannot start cluster transport after generation invalidation.

### Receiver-session finalizer: `0x66a40..`

- `0x66a80..0x66a94`: reads a callback pointer from session offset `+0x20`; if nonzero it invokes the pointer via `blx r3` with session in `r0` and `session+0x18` in `r1`.
- The finalizer then calls several cleanup routines, releases and zeroes state, and destroys a mutex at session `+0x80`. The Step 125 range ends at `0x66c00`, before the literal pool and every final exit path have been fully captured.
- We do not yet know whether the native queue retains the receiver session or how the finalizer interacts with native HTTP client shutdown.

## What changes now

The deterministic Step 125 test still proves a scheduling window in `shim_screen_http_send`: a request can pass `combo_prepare_send_locked`, release `g_state_lock`, and proceed toward `http_send` after another thread has invalidated the session. This **does not prove a UAF, callback corruption or device crash**; queue retention may mitigate some hazards. It also does not prove the request is protocol-safe to send after teardown.

Do **not** fix this by holding `g_state_lock` during native send, blocking the finalizer, or releasing native CF objects speculatively. There is currently insufficient evidence to choose a safe synchronization strategy.

The existing response-ticket cancellation, generation validation, message identity match, and forbidden combined-mode package output remain in place.

## Next read-only evidence

Run the checked-in `scripts/step126_extract_ownership_and_dispatch.sh` on the user's Mac and review `~/Desktop/AK3918_step126_ownership_and_dispatch.txt`.

It captures the `0x82c74 / 0x82c78` wrappers, underlying retain/release implementation, queue producer/neighboring consumer, `0xa0454` wake helper, `0xa1338` response completion, and fuller session-finalizer context. The script verifies the exact stock hash and mounts both source and toolchain read-only. It does **not** compile, package, modify, install or flash firmware.

Expected follow-up decisions:

1. Confirm whether the paired calls to `0x82c74` increment both object reference counts.
2. Locate the queue drain and balanced releases and identify the under-mutex indirect callback target.
3. Determine whether the receiver session (not merely the HTTP client/message) can be destroyed while send or response is outstanding.
4. Only then determine whether teardown/send ordering needs a shim barrier or is safely handled by stock object ownership.

**Deployment remains blocked.** `AK_ENABLE_COMBINED_CLUSTER=0` by default; no flashable combined image should be produced.
