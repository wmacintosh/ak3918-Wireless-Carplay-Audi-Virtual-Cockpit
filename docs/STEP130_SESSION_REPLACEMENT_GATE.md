# Step 130 — Phone-command lifetime across session replacement

**Status:** experimental source-only protection and host regression. The patched
AK3918/ARM combined-stream firmware is **not authorized for device installation**.

## Issue

Prior to Step 130, `shim_session_teardown(old)` waited for
`g_session_cmd_inflight` before allowing the stock finalizer to proceed.
However, when `shim_session_setup(new)` replaced a different active session,
it immediately assigned `g_session = new` without first draining phone
commands admitted against the old session. A later old-session finalizer could
observe `g_session != old` and skip the wait even while a detached stream
worker still used the unowned old vendor session pointer through
`send_phone_cmd_safe`.

This is an **identified lifetime ordering weakness in source**, not a confirmed
hardware crash. The older session-lifecycle research separately established
that no validated vendor API safely retains the parent `AirPlayReceiverSession`
for arbitrary asynchronous use.

## Scoped fix in `altscreen.c`

When `shim_session_setup(new)` observes a different session:

1. Set `g_session_valid = 0` under `g_state_lock` to reject new
   `send_phone_cmd_safe` admissions.
2. **Keep `g_session = old` while `g_session_cmd_inflight > 0`**, waiting on
   `g_session_cv` with `pthread_cond_wait` so callbacks and the previous
   command can acquire the mutex.
3. Only after the old commands drain, set `g_session = new` and advance
   `g_session_generation`.
4. Preserve the existing combined-stream build/request cancellations and
   `g_combo_send_inflight` admission wait.
5. Continue to treat the new session as invalid until the original stock
   `SETUP` succeeds; do not access the old vendor session after replacement.

The ordering keeps old-session identity visible to
`shim_session_teardown(old)` until its in-flight phone commands have left,
regardless of whether the old finalizer or new setup wins the mutex after
the command completes.

No vendor `CFRetain` or guessed session-ownership calls were introduced.

## Deterministic test

`tests/run_step130_session_transition.py` extracts the **actual initial
session transition block** from `shim_session_setup`, compiles it on a host
for both `AK_ENABLE_COMBINED_CLUSTER=0` and `=1`, and forces a transition
while one phone-command user is already admitted.

It verifies that:

- invalidation precedes the command drain;
- the old pointer stays published while the command is outstanding, so its
  teardown remains eligible to wait;
- a condition signal permits replacement to complete;
- the new session is not marked valid prematurely;
- the existing combined-mode cancellation remains wired, and the disabled
  mode does not spuriously mutate combined state.

This does not call vendor `session_send_command`, emulate a full AirPlay
`SETUP`, or establish on-dongle safety.

## Four-mode ARM/uClibc cross-build — local pass after Step 130

The user ran `git pull --ff-only` to update the active WIP branch from
`62d34c6` to `6d14d60`, then ran
`bash scripts/step129_validate_arm_matrix.sh` on their Mac.

Their terminal output reported **PASS** for all four configurations:

| Combined stream 111 | Phone commands | ARM/uClibc result |
| --- | --- | --- |
| 0 | 0 | PASS |
| 0 | 1 | PASS |
| 1 | 0 | PASS |
| 1 | 1 | PASS |

The final output said that no binaries, recovery firmware or tar files were
changed in the repository. This is **user-provided local test evidence for
Step 130 source**, not an independent runtime test, proof of successful
CarPlay negotiation, or verification of a flashable patched executable.
GitHub Actions independently passed the source-level Step 130 tests for
commit `6d14d60`.

## Outstanding HTTP transport/callback issues

- Native `HTTPClientSendMessage` and response completion paths are statically
  understood enough for the Step 128 enqueue admission gate. Late response
  wrappers still **always delegate to the stock callback**.
- **Later Step 131 update:** Verified stock `HTTPClientSendMessage` error paths prove a nonzero result bypasses both reference retains and native enqueue. Step 131 now reclaims these never-submitted tickets. This was not part of the Step 130 implementation; accepted submissions that never deliver a callback still retain tracking tombstones. See [Step 131](STEP131_NATIVE_HTTP_FAILURE_RETURN.md).
- The present tests do not reproduce every possible simultaneous session
  setup, native HTTP cancellation, socket interruption, or vehicle reconnect.
  Those require additional evidence and controlled device observation.

## Packaging and branch safety

`AK_ENABLE_COMBINED_CLUSTER` remains disabled by default. The test-only
combined package is still separately opt-in and **unvalidated on the user's
AK3918 dongle**. The project `main` branch, stock recovery archive and
previously tested historical package must not be replaced or flashed
as a consequence of this Step 130 source change.

**Next safe work:** deeper native HTTP send-return/error-path verification and
reconnect stress tests; only reclaim tombstones on proven no-enqueue branches.
