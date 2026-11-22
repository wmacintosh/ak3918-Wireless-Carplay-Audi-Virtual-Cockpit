# Step 140 — Combined stream-111 compatibility: source-derived request/response integration

**Status:** source-level integrated host contract checks and opt-in hook isolation. **No change to `altscreen.c`, `build_hook.py`, stock recovery, patched ELF, packaged firmware, `main` or device configuration.** This is *not* a demonstration that CarPlay video reaches the Audi Virtual Cockpit.

## Goal

After Steps 137–139 closed the theoretical allocator-failure diversion without a dispatcher patch, return to the functional combined stream-111 path. Preserve the normal stream-110 SETUP contract while testing the *actual experimental source bodies* from native stream-array ensure through outgoing HTTP send, combined reply parsing, stock callback and candidate worker dispatch.

The verified original ARM callsites remain:

- `0x2fadc`: original native stream-array ensure call (stock BL target `0x9327c`).
- `0x2fbb0`: original native `HTTPClientSendMessage` call (stock BL target `0xa6974`).
- `0x2ec7c`: original stock screen-response callback; signals the SETUP waiter after its own processing.
- `0x2fc54`: original response wait path for zero HTTP send result; not modified.

## 1. Feature-flag boundary — source review

In `build_hook.py`, screen hooks are installed exclusively inside `if ENABLE_COMBINED_CLUSTER:`:

| Feature | Combined disabled (default) | Combined enabled (experimental) |
| --- | --- | --- |
| Patch `0x2fadc` to stream-ensure shim | **No** | Yes, after original BL instruction verification |
| Patch `0x2fbb0` to send shim | **No** | Yes, after original BL instruction verification |
| Reserve two extra screen hook pointer slots | **No** | Yes |
| Export/initialize `shim_screen_ensure_stream`, `shim_screen_http_send` | Excluded by `#if AK_ENABLE_COMBINED_CLUSTER` | Yes |
| Original setup/finalizer hooks and five baseline altScreen/display patches | Remain part of historical hook build | Remain part of experimental hook build |
| Combined stream-111 packaging under legacy `ak_hook.tar` flag | N/A | **Rejected**; distinct explicit test-only plan |

**Important distinction:** “combined disabled” does **not** mean the whole historical patched binary is byte-identical to pristine stock. The older setup/finalizer hooks and five display-related changes exist independently of combined stream 111. The claim is limited to **two additional combined-screen hook sites** being unmodified when the flag is off.

`tests/test_step140_feature_isolation.py` checks the actual Python AST branch and both BL/slot arguments, and uses the host C preprocessor to confirm the two combined-screen function bodies and constructor pointer assignments disappear with `AK_ENABLE_COMBINED_CLUSTER=0`. It does not run `build_hook.py` or write any ELF.

## 2. C path under test — unmodified extracted source

`tests/run_step140_stream111_contract.py` compiles these **unmodified function bodies extracted directly from `altscreen.c`**, together with the original request-tracking/admission helpers:

- `shim_screen_ensure_stream`
- `shim_screen_http_send`
- `combined_response_port`
- `shim_screen_response`
- Step 115/120/128 metadata and send-admission helpers

The test supplies deterministic host-only implementations of CF arrays, CF dictionaries, message serialization *results*, HTTP send return, stock callback and worker scheduling. The stubbed Core Foundation functions model reference ownership and inspect that CF/HTTP calls do **not** occur with `g_state_lock` held. Only the host's worker scheduling is made synchronous to check branch outcomes; this deliberately does not model real native thread timing.

### Cases exercised

| Host case | Required source behavior |
| --- | --- |
| Current, unpaired, valid native SETUP | Preserve original stream **110** as first array entry, add one **111** dictionary (`Type=0x6f`), populate UUID-derived nonzero connection ID, UUID and latency, then publish a correlated request |
| Matching HTTP send and valid combined reply | Replace only the outgoing response callback, keep native SETUP message context, consume exactly one ticket, call **stock `0x2ec7c` callback once**, and schedule a worker with the validated 111 dataPort and matching connID/generation |
| No valid phone-side session | Leave the stream array as stock 110 only, do not claim a ticket, and forward native HTTP send unchanged |
| Pair-verify active | Preserve stock 110, omit 111 and its optional tracking |
| UUID-derived connection ID zero | Preserve stock 110 and release the unpublishable combined candidate |
| Combined 111 with missing HTTP client | Reject known combined send **before** native HTTP, reclaim definitely unsubmitted metadata |
| Native nonzero preparation error | Reclaim only the proven pre-dispatch ticket, as established by verified Step 131 ARM behavior |
| Native response after generation cancellation | Keep tombstone until response, call stock callback once, **never** start a cluster worker for stale generation |
| Reply with 111 dataPort outside `1..65535` | Reject optional worker but always invoke the stock callback |

These scenarios test a *host source contract*, not whether an Audi head unit, wireless dongle or iPhone accepts or delivers the combined stream.

## 3. Host ABI and simulator limitations

The original AK3918AN uses **32-bit ARM**. The native message's body pointer at `+0x49c` and body length at `+0x4a0` are adjacent **four-byte** fields. On GitHub's 64-bit Linux host, a direct C `void *` read at `+0x49c` overlaps the length field; the deterministic CF stub uses an opaque, never-dereferenced pointer token with a synthetic upper word so the **same original source** can follow its branch. This does **not** validate actual native layout, plist data or serialization. The test enables UBSan checks other than **host pointer alignment**, which is incompatible with the original ARM32 message field layout; existing ARM/uClibc local compilation coverage is separate and more relevant for ABI.

The worker function `cluster_setup_to_car` is a stub recording intended `generation,connid,data_port`; no socket, AES/ChaCha, RTSP, display render, or cluster transport is exercised. The stub for the stock callback records delegation, not implementation of the full native `0x2ec7c` signal processing. Concurrency, teardown interleavings, target-side buffer ownership, original 110 response semantics, and on-device visual output remain unvalidated.

The stock receiver sender's `0x2fc54` forever wait and the Step 115 callback-tombstone failure policy remain unchanged.

## 4. Safety and next research gate

The source contract should be treated as **passing only after GitHub Actions confirms the real extracted function test and feature-flag isolation test**. A green host run cannot make this experimental firmware safe to deploy.

Next, perform a **source-only review of the car-side media path** downstream of a valid stream-111 dataPort: socket connection and generation checks, session key readiness, stream-key derivation, packet construction, encrypted payload routing and the Virtual Cockpit-facing protocol. Locate the smallest independently verifiable host fixture for an actual synthetic 111 payload. Do not alter native dispatch ownership or move to firmware packaging/flashing based on these host checks.
