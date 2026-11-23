# Step 126 — Stock HTTP ownership and dispatch audit

**Status (2026-11-21): static, read-only evidence. No firmware deployment.**

Input: user-supplied `AK3918_step125_native_http_transport.txt` (712 lines), disassembled from the SHA-256-verified AK3918AN stock `sdDongle`:

`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`

The code under test is the existing OMKE-based AK3918 ARM port on `wip/ak3918-step115-callback-tombstones`, not OMKE's MIPS AX1800M firmware.

## Confirmed from Step 125 ARM instructions

### Stock HTTP send: `0xa6974..0xa6a7c`

- `0xa6a08..0xa6a3c`: initializes per-message send/buffer pointers, including `msg+0x8bc`, `+0x8c0`, `+0x8c4`, `+0x8c8`, `+0x8cc`, `+0x8d0`.
- `0xa6a4c`: calls `0x82c74` with `r0=msg`; `0xa6a54`: calls the **same** function with `r0=client`. Step 126 resolves `0x82c74 -> 0x85b50` and validates its ordinary (non-constant, typed CF object) path: at `0x85bd4..0x85bdc`, it calls `0xf0090` on object offset `+4` with increment `+1`. Its counterpart `0x82c78 -> 0x85c04` decrements via `0xf0090(...,-1)` at `0x85c88..0x85c90`; the zero-result path calls an object-specific finalizer and `free@plt` at `0x85cbc..0x85cd0`. **Reference increment/decrement behavior is confirmed for this path**, though dispatch ownership and session retention still require separate proof.
- `0xa6a5c`: stores the client pointer into `msg+0x8ec`.
- `0xa6a68..0xa6a6c`: takes `*(client+8)` as queue-object input `r0`, passes the message as `r1`, passes a static function/data pointer as `r2`, and calls `0xa1900`. The stock send returns through `0xa6a74..0xa6a7c`.

**Implication:** The native send has an explicit reference-management and queue handoff boundary. The send call **increments** references for message and HTTP client before enqueue under the standard CF-object path; the remaining question is whether the queued references are balanced by the queue drain, and whether the *receiver session* has independent lifetime protection. Even confirmed message/client retention would **not**, by itself, prove receiver-session lifetime safety.

### Native transport queue: `0xa1900..0xa1b20`

- `0xa1978..0xa19d0`: allocates a 12-byte node with `calloc(1,12)`; saves the incoming message in node offset `+8` and incoming secondary argument in `+4`.
- `0xa19d4..0xa19d8`: locks a native mutex stored at queue-object offset `+0x2c`.
- `0xa19f0..0xa19fc`: appends the node to the queue's linked-list tail (`queue+0x34` and the previous tail).
- `0xa1a18`: signals a condition variable in a special queue state.
- `0xa1a20`: calls `0xa18d8`, a helper that in turn calls `0x8f564` and `0x8f078`.
- `0xa1a34..0xa1a3c`: if a process-level indirect callback is installed, invokes it through `blx r3` with `r0=0`, **before releasing the native queue mutex**.
- `0xa1b14..0xa1b20`: exits by calling `pthread_mutex_unlock` on the same mutex.

**Implication:** Blindly holding the shim's `g_state_lock` throughout `http_send` would create a possible lock-order/reentrancy hazard. The indirect callback takes `r0=0`, so it is **not demonstrated to be** the direct `shim_screen_response(msg)` callback; it may merely wake the queue. Its target and the queue consumer are unknown.

### Adjacent socket initializer is not a queue drain

The Step 126 excerpt `0xa1b74..0xa1e00` starts an adjacent routine that creates a socket (`socket@plt` at `0xa1bec`), binds it (`0xa1c6c`), obtains local socket info and connects (`0xa1d84`). It can enqueue work through `0xa1900` at `0xa1df4`. **This is a queue producer/initializer, not evidence of a queue consumer or reference release.** The real drain still needs discovery.

### Response synchronization primitive: `0xa1338..0xa13a8`

The stock callback's `0xa1338` helper locks `object+0x2c`, increments the counter at `object+0x64`, signals the condition variable pointer in `object+0x60`, and unlocks. This is a completion-notification path; it is not evidence that the receiver session is retained. It strengthens the need to avoid introducing lock-order inversions in our shim.

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

1. Confirm exact CF object classes of both native send arguments and locate balanced release of their newly retained references after queue completion.
2. Locate the **actual queue drain** (not adjacent socket initialization at `0xa1b74`), its release/error paths, and the global indirect callback invoked under queue mutex at `0xa1a3c`.
3. Determine whether the receiver session (not merely the HTTP client/message) can be destroyed while send or response is outstanding.
4. Only then determine whether teardown/send ordering needs a shim barrier or is safely handled by stock object ownership.

**Deployment remains blocked.** `AK_ENABLE_COMBINED_CLUSTER=0` by default; no flashable combined image should be produced.

## Step 126 uploaded disassembly review (2026-11-21)

The user's verified stock report supplied the exact `0x82c74/0x82c78` forwarding wrappers and the underlying CF retain/release code, as well as fuller finalizer instructions. At `0x66a94` the session finalizer calls a session-owned function pointer from `session+0x20` before significant cleanup; it then destroys a session mutex (`0x66b34`), releases `session+0x0c` via the CF release wrapper (`0x66ba8`), and tears down other synchronization objects (`0x66bbc`, `0x66bd4`). **No demonstrated guard prevents session finalization while a separate HTTP enqueue is active.** This continues to be a source-only logical race, not a demonstrated runtime use-after-free. See `scripts/step127_extract_queue_completion.sh` for targeted investigation of the native queue callback at `0xa6040`.
