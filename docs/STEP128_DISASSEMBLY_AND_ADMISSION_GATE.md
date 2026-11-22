# Step 128 — Stock Queue Release Proof, Session Independence Audit, and Send-Admission Gate

**Status (2026-11-21): static disassembly resolved + host-tested send-admission gate; no combined-mode flashing or packaging permitted yet.**

All addresses below are verified directly against the SHA-256–matched stock ARM `sdDongle`:
`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.

---

## 1. Where the native queue releases both `http_send` references (`0xa6974`)

In `HTTPClientSendMessage` (`0xa6974`), `0xa6a4c` retains `msg` (`CFRetain`, `0x82c74`) and `0xa6a54` retains `client` (`CFRetain`, `0x82c74`), stores `client` at `msg+0x8ec` (`0xa6a5c`), and **attempts to enqueue** `0xa6040(msg)` onto `client->queue` via `dispatch_async_f` (`0xa1900` at `0xa6a6c`).

Disassembly confirms both retains are cleanly balanced:

1. **Dispatch queue drain (`0xa304c..0xa30b0`)**:
   - Pops the 12-byte work node from `queue+0x30`.
   - **Unlocks `queue+0x2c` at `0xa3080` before invoking the callback**, then executes `blx r3` (`0xa308c` → `0xa6040(msg)`) and frees the 12-byte node (`0xa3094`, `free@plt`).
2. **`client` released at `0xa6070` (`_HTTPClientSendMessage`, `0xa6040..0xa6070`)**:
   - Reads `r4 = *(msg + 0x8ec)` (`0xa6044`).
   - Appends `msg` onto `client`'s internal singly linked list (`client+0x49c` head / `client+0x4a0` tail, `0xa6048..0xa605c`), transferring ownership of `msg`'s `+1` retain into `client->messageList`.
   - Calls `_HTTPClientRunStateMachine(client)` (`0xa53fc` at `0xa6064`).
   - Tail-calls **`b 0x82c78` (`CFRelease(client)`)** at `0xa6070`, balancing `0xa6a54`.
3. **`msg` released at `0xa4c58` (`_HTTPClientCompleteMessage`, `0xa4c18..0xa4c58`)**:
   - Pops `msg` from `client+0x49c` (`0xa4c18..0xa4c30`) and stores completion status at `msg+0x8e8` (`0xa4c40`).
   - Invokes `msg->completion(msg)` (`msg+0x904`) at `0xa4c4c` (`blx r3`).
   - Tail-calls **`b 0x82c78` (`CFRelease(msg)`)** at `0xa4c58`, balancing `0xa6a4c`.
   - Therefore `shim_screen_response` is guaranteed to run **while `msg` is still retained**.
4. **Error / invalidation path (`0xa6584` → `0xa4f30` → `0xa4d7c`)**:
   - `HTTPClientInvalidate` (`0xa6584`) retains `client` (`0xa658c`) and enqueues `_HTTPClientInvalidate` (`0xa4f30`) onto the same serial `client->queue` (`0xa65a4 → 0xa1900`).
   - `0xa4f30` calls `_HTTPClientErrorHandler(client, -6723)` (`0xa4d7c`, `kCanceledErr`), which drains every remaining `msg` on `client+0x49c` via `0xa4c18` (`0xa4eac..0xa4ec4`, invoking `msg+0x904` and releasing `msg`), then releases `client` at `0xa4f48`.
5. **Non-blocking enqueue confirmation**:
   - `HTTPClientSendMessage` (`0xa6974`) is a nonblocking **attempted enqueue**: it never invokes `0xa6040` or `msg+0x904` synchronously on the caller's stack. **Step 133** proves the async dispatcher can fail to allocate a work node and return without inserting one, while the HTTP sender still returns zero; see [Step 133](STEP133_QUEUE_OWNERSHIP_AND_FINAL_RELEASE.md).
   - The indirect notifier at `0xa1a3c` in `0xa1900` runs only when `queue == dispatch_get_main_queue()` (`0xa1a04..0xa1a0c`).

---

## 2. Receiver session (`0x66a40`) independence and `g_session` audit

- **Can `AirPlayReceiverSession` (`0x66a40`) finalize while a SETUP HTTP request is outstanding?** **Yes.**
  - The hooked SETUP sender `0x2f6b8` (containing `0x2fadc` and `0x2fbb0`) is called by `0x30374` (`0x3047c`), which takes **no `AirPlayReceiverSession` argument**.
  - At `0x2fba4..0x2fbac`, `0x2f6b8` loads a **global car-side `HTTPClientRef`** (`GOT + 0x75c`, invalidated separately at `0x2a76c..0x2a79c`, `0x29dc4`, `0x2a3dc`), enqueues via `0xa6974`, and blocks on its local semaphore (`dispatch_semaphore_wait` at `0x2fc54`) until `0x2ec7c` signals `0xa1338`.
  - `AirPlayReceiverSession` (`0x66a40`) is the **phone-side** session with its own `eventClient` (`session+0x3ec`, invalidated at `0x613a4`) and its own queues (`session+0x08`, `session+0x3d0`), with no refcount or lock coupling to `g_httpClient`.
- **Audit of `g_session` in `altscreen.c`**:
  - `open_alt_sink(session, ...)` runs synchronously inside `shim_session_setup` and snapshots the session key before returning.
  - `send_phone_cmd_safe` (optional `AK_ENABLE_PHONE_CMDS`) is already gated by `g_session_cmd_inflight` and drained by `shim_session_teardown` on `g_session_cv`.
  - All other uses (`combo_prepare_send_locked`, `combo_consume_response_locked`, `shim_screen_ensure_stream`, `shim_screen_response`, `cluster_setup_to_car`, `sink_generation_current`) only compare `g_session != NULL` and never dereference it.

---

## 3. Step 112 `cf_release(replaced_streams)` ownership proof (`0x9327c`)

Disassembly of `0x9327c` (`CFArrayEnsureCreatedAndAppend`, called at `0x2fadc` with `&sp[0x34]`):

- When `*ioArray == NULL`, `0x932b8` calls `0x82e10` (`CFArrayCreateMutable`, returning a `+1` owned reference) and stores it at `*ioArray` (`0x932c0`), then appends `stock_video` via `0x82fc0` (`0x93310`).
- `0x2faec` (`0x836dc`) inserts `*sp[0x34]` into `reqDict` (retaining it inside the dictionary).
- `0x2fe1c..0x2fe28` releases `*sp[0x34]` once via `0x82c78` (`CFRelease`).

Therefore, when `shim_screen_ensure_stream` replaces `*streams` with a newly created `CFArrayCreateMutable`, releasing the displaced original array via `cf_release(replaced_streams)` is **required and balanced**.

---

## 4. Step 128 send-admission gate (`g_combo_send_inflight`)

Because `0xa6974` is a nonblocking dispatch attempt that never acquires `g_state_lock` or invokes `shim_screen_response` synchronously, regardless of queue-node allocation success:

- `shim_screen_http_send` increments `g_combo_send_inflight` (`combo_send_enter_locked`) under `g_state_lock` when `decision == 1`, releases `g_state_lock`, invokes `http_send(client, msg)`, and then calls `combo_send_leave_locked` under `g_state_lock` (canceling the ticket on `rc != 0` and broadcasting `g_session_cv` when `g_combo_send_inflight` hits `0`).
- `shim_session_teardown` and generation transitions in `shim_session_setup` invalidate `g_session_valid` / cancel builds & requests first, then wait on `g_session_cv` until `g_combo_send_inflight == 0` (`combo_wait_sends_drained_locked`).
- `tests/run_step128_admission_gate.py` extracts the Step 115/120/128 helpers directly from `altscreen.c` and verifies serialization, post-teardown rejection, non-deadlocking concurrent response callbacks, and failed-send cleanup under ASan/UBSan, UBSan, and unsanitized builds.

## 5. ARM926EJ-S / uClibc cross-compile & ELF verification

Compiled and validated inside `ak3918-buildroot:latest` (`arm-buildroot-linux-uclibcgnueabi-gcc`, `-mcpu=arm926ej-s -mfloat-abi=soft`):

- `AK_ENABLE_COMBINED_CLUSTER=0`: `PASS: ELF32 ARM, soft float, uClibc dependency, constructor, exported hook`; `libSdH.so` links `libc.so.0`; `sdDongle` MD5 `4aafec684a5f46ccd16704f0a0a317a7`.
- `AK_ENABLE_COMBINED_CLUSTER=1`: `PASS: ELF32 ARM, soft float, uClibc dependency, constructor, exported hook`; `libSdH.so` links `libc.so.0`; hooks at `0x2fadc -> 0x102ea0` (`0x13c644`) and `0x2fbb0 -> 0x102eac` (`0x13c648`); `sdDongle` MD5 `bf66fb161209ad484324a015e308847b`.

## Controlled on-dongle test gate

- `AK_ENABLE_COMBINED_CLUSTER` remains `0` by default and the legacy `AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=1` veto remains active.
- An explicit test-only archive `ak_hook_step128_test.tar` can be built with `AK_ENABLE_COMBINED_CLUSTER=1 AK_STEP128_ALLOW_TEST_PACKAGE=1` without modifying `stock_ak_202610081659.tar` or the default `ak_hook.tar`.
- Keep verified `stock_ak_202610081659.tar` ready for immediate recovery.
