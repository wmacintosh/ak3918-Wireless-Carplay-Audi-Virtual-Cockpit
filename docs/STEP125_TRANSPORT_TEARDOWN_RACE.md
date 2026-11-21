# Step 125 — Native HTTP-send / session-finalizer race audit

**Status (2026-11-21): confirmed source-level concurrency blocker; NOT safe to flash combined stream 111.** The experimental combined mode remains off by default. The test below deliberately reproduces a failure ordering; success means the blocker is still present.

## Verified AK3918 evidence

Step 121 captured the verified stock ARM `sdDongle` executable (SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`):

- `0x2fadc`: stock stream-array ensure (experimental shim can inject stream 111).
- `0x2fb04`, `0x2fb58`: independent failure decisions can bypass sending after publication.
- `0x2fb90`: stock writes the response callback at `msg+0x904`.
- `0x2fbac`: native client pointer is loaded into `r0`; `0x2fbb0` calls stock `http_send(client,msg)`.
- `0xa6974`: stock `http_send` implementation. It prepares message fields, including `msg+0x8bc..0x8d0`, and calls an internal transport/dispatch routine at `0xa1900` (`0xa6a68`) on its success path. The current Step 121 disassembly does **not** include the body of `0xa1900`, so synchronous callback behavior and transport lifetime are unverified.
- `0x2fe1c..0x2fe38`: native SETUP cleanup releases the outgoing CF array and local HTTP message.
- `shim_session_finalize` calls `shim_session_teardown` before the stock finalizer. Under `g_state_lock`, teardown marks session invalid and cancels combined builds/requests.

## Deterministic negative regression

`tests/run_step125_teardown_race.py` compiles the current Step 115/120 helper implementation from `altscreen.c` in a host C harness. Two pthreads synchronize to force:

1. A combined build matching the exact native HTTP message pointer is accepted by `combo_prepare_send_locked`.
2. The send path releases `g_state_lock`.
3. Another thread invalidates the session and cancels the outstanding request.
4. The original sending thread proceeds toward `http_send` despite the now-invalid session.

This matches the *ordering* in `shim_screen_http_send`: there is no barrier between the lock release and `http_send`. The host test does not invoke the stock ARM transport or prove an on-device crash. It merely proves the source admits this interleaving.

## Why not solve this by simply locking around `http_send`?

Doing so might serialize teardown, but it also holds an application lock during unreviewed native transport code. The stock call reaches `0xa1900`, whose callback/reentrancy behavior has not yet been verified. If native send dispatches a synchronous response or a teardown callback that also needs the lock, an unconditional mutex could deadlock. A correct protocol may require an explicit transport admission barrier, pinned session lifetime and a carefully ordered nonblocking finalizer.

**Do not introduce such a lock until the stock send, dispatch, response callback and finalizer paths are understood.**

## Read-only Step 125 extraction

From the existing GitHub clone on the Mac with the verified stock ELF and Docker ARM buildroot:

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step125_extract_native_transport.sh
```

This generates `~/Desktop/AK3918_step125_native_http_transport.txt` by disassembling:

| Range | Intended audit |
| --- | --- |
| `0xa6974..0xa6a98` | Native HTTP send entry and direct calls |
| `0xa18c0..0xa1b80` | `0xa1900` internal transport dispatch and surrounding code |
| `0x2ec60..0x2ef80` | Stock screen SETUP response callback |
| `0x669e0..0x66c00` | Receiver session finalize function |
| `0xa6d08..0xa6e50` | Native HTTP message construction |

The script verifies stock checksum, uses read-only Docker mounts, writes to a temporary file first and checks expected instructions before publishing its local report. The extracted ranges are review targets, not confirmed function bounds.

## Packaging block

`build_hook.py` now rejects `AK_ENABLE_COMBINED_CLUSTER=1` together with `AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=1` **before doing any build or patching work**. The opt-in flag cannot emit a new combined stream-111 tar while this race is unresolved. Existing local/repo firmware archives are untouched; do not flash them.

`tests/test_step125_package_gate.py` verifies that early rejection. GitHub CI runs the negative race reproduction, read-only script syntax check and package-veto test.

## Remaining questions

1. Can the stock `http_send` / `0xa1900` path invoke the response or teardown synchronously?
2. What retains the HTTP message and session while the native HTTP queue is active, and when is the reference released?
3. Can the session finalizer race an active `http_send` and safely return before that send completes?
4. Can native cancellation be coordinated without blocking an event loop or introducing a lock inversion?
5. Are stock error cleanup and callback cancellation still valid on the exact AK3918 ARM/uClibc build?

**No runtime/deployment approval is implied by passing host tests.** Preserve the known-good MMI and verified stock recovery firmware.
