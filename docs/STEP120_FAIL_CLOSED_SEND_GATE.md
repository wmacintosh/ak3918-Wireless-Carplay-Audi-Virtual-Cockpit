# Step 120 — fail-closed outgoing stream-111 send gate (WIP)

## Why this patch exists

The stock MIB2 outgoing-screen request function is known to construct its stream array at `0x2fadc`, insert that array into a dictionary at `0x2faec`, serialize/build the HTTP message, and call the HTTP send routine at `0x2fbb0`. At `0x2fbb0`, a nonzero return branches to stock error handling and eventually to the normal cleanup path, which releases the message and local CF references.

Earlier Step 115 code validated generation only when *installing the response callback*. It still called the original HTTP send routine if metadata was canceled or no response slot was available, potentially sending an untracked, already-serialized stream-111 request.

## Changes in `altscreen.c`

1. Add a canceled flag to `combo_build`, and preserve canceled build records when a session is finalized or generation changes. Earlier code erased these records with `memset`.
2. Refuse to overwrite any unfinished build record owned by the current thread. If the native code exits before reaching the send hook, the record may remain and block subsequent instrumentation; this is intentional fail-closed behaviour.
3. Add `combo_prepare_send_locked`, returning:
   - `0`: no tracked stream-111 build; preserve stock HTTP send unchanged.
   - `1`: tracked build, current generation and session, valid stock callback pointer, and successful response-tracking registration; install response shim and call stock send.
   - `-1`: tracked stream-111 build is stale or cannot be tracked; return a nonzero error to the native caller without calling stock HTTP send.
4. Keep CoreFoundation operations and the native `http_send` call **outside** `g_state_lock`, avoiding the known reentrancy hazard.
5. Preserve Step 115 request tombstones and ticket-based cancellation.

This gate acts only on outgoing messages whose stream-111 build metadata reaches the same native send hook on the same thread. It does not attempt to edit serialized plist bytes.

## Offline validation

- Native host C syntax with `-Wall -Wextra -Werror` passed for both `AK_ENABLE_COMBINED_CLUSTER=0` and `=1`.
- `tests/run_step120_host.py` extracts the actual Step 115 and Step 120 C helper code and passes focused tests under `-fsanitize=address,undefined`, `-fsanitize=undefined`, and without sanitizers. Coverage includes the unmodified stock path, normal claim, teardown after array creation, generation mismatch, incompatible callback, message-address collision, saturated request slots, pending canceled builds, and send-error ticket cancellation.
- **Target ARM/uClibc compilation of this Step 120 revision has not yet been run on the user's Mac.**
- No device runtime test, package, or flash was performed.

## Unresolved blockers

**Time-of-check/time-of-use (TOCTOU) send race (deployment blocker).** Teardown can still invalidate a session **after** `combo_prepare_send_locked` releases `g_state_lock` but before/during the native HTTP send. This patch does not provide a strict atomic teardown-to-transport guarantee. Resolving that requires proven native HTTP send/reentrancy and finalizer ordering; holding `g_state_lock` across native code is not considered safe without such evidence.

**Thread and request correlation.** `pthread_self()` matches the original array-construction and send hooks within the same native function under ordinary synchronous execution. If that function can reenter or perform different outbound sends on the same thread between hooks, records may be mismatched. Verify native control flow and test on target in a recoverable environment before relying on it.

**Orphaned build / stock-110 misassociation (deployment blocker).** The stock serialization helper at `0x2fafc` has failure branches that can bypass the send hook. If the prior stream-111 build record remains and another request is built on the *same thread*, the next call to the send hook may consume the orphaned record and incorrectly associate it with a **stock-110-only** message. Depending on generation state, this can reject the legitimate stock request or install an unnecessary response wrapper. The current test suite checks isolated send-gate helpers; it does **not** prove whole-function request identity. This must be fixed by a verified request/frame identity or a cleanup hook before experimental combined mode is eligible for deployment.

**Failed sends and late callbacks.** Step 115 retains tombstones to avoid reusing callback identities. Eight orphaned requests can exhaust the tracking table. Callback pointer identities also depend on the stock HTTP object's lifecycle.

**Abort semantics.** The disassembly supports nonzero send-status error cleanup, but this change has not been observed executing on the dongle. The native error path and exact HTTP message ownership should still be validated on the actual firmware before enabled deployment.

## Safety and next action

Maintain `AK_ENABLE_COMBINED_CLUSTER=0` for any ordinary recovery or stock builds. This remains an experimental source-only branch. No firmware packaging or flashing.

Next: rerun ARM syntax checks for Step 120, then investigate native serialization failure cleanup and request/frame identity **before** treating this send gate as safe. Independently investigate HTTP send/finalizer concurrency for the TOCTOU window.
