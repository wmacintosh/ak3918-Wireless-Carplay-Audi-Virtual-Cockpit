# Step 125 — Native HTTP-send / session-finalizer race audit

**Status (2026-11-21): confirmed source-level concurrency blocker; NOT safe to flash combined stream 111.** The experimental combined mode remains off by default. The test below deliberately reproduces a failure ordering; success means the blocker is still present.

## Verified AK3918 evidence

Step 121 captured the verified stock ARM `sdDongle` executable (SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`):

- `0x2fadc`: stock stream-array ensure (experimental shim can inject stream 111).
- `0x2fb04`, `0x2fb58`: independent failure decisions can bypass sending after publication.
- `0x2fb90`: stock writes the response callback at `msg+0x904`.
- `0x2fbac`: native client pointer is loaded into `r0`; `0x2fbb0` calls stock `http_send(client,msg)`.
- `0xa6974`: stock `http_send` implementation. It prepares message fields, including `msg+0x8bc..0x8d0`, calls the same reference-management helper `0x82c74` on both the message (`0xa6a4c`) and client (`0xa6a54`), stores the client at `msg+0x8ec` (`0xa6a5c`), and calls native transport enqueue `0xa1900` (`0xa6a6c`). Step 125 now captures `0xa1900` and shows its lock/queue behavior. Whether `0x82c74` actually increments references, and how the queue drains, still require verification.
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

Doing so might serialize teardown, but it also holds an application lock during unreviewed native transport code. At `0xa19d4..0xa1b20`, the enqueue path holds a native mutex at queue-object offset `0x2c`. At `0xa1a3c`, it can invoke an indirect process callback while that mutex is held (argument `r0=0`); this is not confirmed to be the HTTP response callback. If a callback or notifier indirectly reenters shim session teardown, holding `g_state_lock` across the native call could deadlock. The queue consumer is not yet traced. A correct protocol may require an explicit transport admission barrier, pinned session lifetime and a carefully ordered nonblocking finalizer.

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

1. What is the indirect function invoked by `0xa1a3c` under the queue mutex, and can it reenter any shim path?
2. Do the paired calls to `0x82c74` retain the message and HTTP client, and what releases them? This is distinct from retaining the receiver session.
3. Can the session finalizer race an active `http_send` and safely return before that send completes?
4. Can native cancellation be coordinated without blocking an event loop or introducing a lock inversion?
5. Are stock error cleanup and callback cancellation still valid on the exact AK3918 ARM/uClibc build?

**No runtime/deployment approval is implied by passing host tests.** Preserve the known-good MMI and verified stock recovery firmware.

## Step 125 report received — 2026-11-21

The uploaded `AK3918_step125_native_http_transport.txt` includes the complete `0xa1900..0xa1b20` enqueue path, stock screen response at `0x2ec7c..0x2ee8c`, and the beginning of the session finalizer at `0x66a40`. The source-level send-after-teardown ordering is still reproducible, but **the report does not establish a use-after-free**: the stock send invokes a reference-management helper on both client and message before enqueue. See [Step 126 ownership and dispatch review](STEP126_HTTP_OWNERSHIP_AND_DISPATCH.md) for precise evidence, unresolved interpretation and the follow-up read-only disassembly. The Step 125 script and previously generated report remain unchanged.
