# AK3918AN session lifetime audit (compile-only branch)

## Evidence from stock sdDongle

- `0x673e4`: `ldrb ip, [r0, #974]` (`0x3ce`), dispatch guard; `0x673fc` loads command handle from session `+0x3d0`; `0x67408` calls `0xa2488`.
- `0x67e00–0x67e04`: writes literal `1` to session `+0x3ce`; this is command-channel activation, **not** a session-alive guarantee.
- `0x66df0`: stores created command-channel handle at session `+0x3d0`.
- `0x66aec` and `0x6777c`: pass the channel handle to `0xa2488` during cleanup paths; **`0xa2488` is not proven to be a destructor**. Its body validates a dispatch object, sets up local mutex/condition-variable synchronization, and calls `0xa1900`.
- `0x66bc8–0x66bdc`: frees command-channel handle via `0xa04bc` and zeros session `+0x3d0`. Commands racing teardown may dereference stale session or command-channel pointers.
- `0x82c78` is a generic reference-counted CF-style release, but there is **no evidence** that the vendor session `r0` is a CF-style object. Do not apply it to a session without an object-type proof.
- HTTP message `+0x904` callback and `+0x8fc` hook callback state have separate ownership; the vendor HTTP message's cleanup does not prove custom callback-state reclamation.

## Follow-up disassembly: dispatch implementation (2026-11-20)

- `0xa3448` calls `0xa1e6c`, and takes a path through `0xa0800` if no dispatch context is returned. The call alone does not establish a session retain.
- `0xa240c` calls `a1e6c` and, on the null-context path, retrieves thread-specific data through `pthread_getspecific`.
- `0xa2488` validates the channel object and an apparent count at `+4`; it prepares a stack-local mutex/condition variable, invokes `0xa1900` and then synchronizes. These steps suggest dispatch coordination, **not** standalone memory destruction or parent-session lifetime management.
- No path yet establishes a retain/release API for the parent session pointer or any safe shutdown callback. Do not call these internal functions as guessed retain/release primitives.
- Follow-up target: inspect `0xa1900` (queue/dispatch path) and the remaining part of `0xa2488` (`0xa26dc–0xa26f4`) to understand completion ordering. Separately trace which allocator/destructor owns the parent session allocation.

## Current experimental hook risks

1. `sink_thread` still holds `snapshot.session` and asynchronously calls `send_phone_cmd` (showUI and forceKeyFrame).
2. `sink_thread` also reads session `+0x3ec` and invokes vendor stream-key derivation using session-relative addresses. Generation comparisons only constrain *logical* staleness: they do not retain memory against concurrent destruction or address reuse (ABA).
3. Callback reply records are intentionally retained after timeout/completion because the vendor may dispatch them later. This is bounded by one SETUP attempt per generation in the normal path, but repeat sessions can still grow memory use.
4. Cross-session socket writes are guarded; their contexts stay allocated to avoid concurrent snapshot UAF.
5. Existing ELF32/soft-float/uClibc/constructor/exported-hook checks are **build checks only**, not real-device safety validation.

## Safe remediation criterion

Before modifying session pointer ownership, identify in **this exact stock firmware** a function that either retains the vendor session across threads, or a session-teardown callback that can synchronously quiesce any active sink and wait for in-flight uses before destruction. Merely checking the command-channel ready byte `+0x3ce` is insufficient.

A promising alternate architecture is copying necessary key material while synchronously inside `shim_session_setup`, then passing **only owned key bytes and a generation** into the sink. It must first be verified that key derivation succeeds at SETUP time; existing `showUI` and `forceKeyFrame` dispatch would otherwise be lost or moved unsafely.

## Next stock binary questions

1. Does `0xa1900` enqueue a callback, execute synchronously, or hold a reference until completion? What does the final `0xa2488` wait do?
2. What does `0xa0800` release, and is that a dispatch-context reference rather than the command-channel object?
3. Which function frees the **session allocation**, and does it notify all other threads before doing so?
4. Does the vendor send-command operation retain its session internally on entry? If so, how is the entry itself protected from concurrent free?
5. At what point in SETUP does `get_stream_keys` (at `0x654c0`) succeed?

## Investigation command (read only)

```bash
REPO="$HOME/AK3918_Diagnostics/ak3918-sigsegv-fix"
docker run --rm --platform linux/arm64 \
  -v "$REPO/stock_analysis:/stock:ro" \
  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro \
  --entrypoint /bin/bash ak3918-buildroot:latest -c '
OBJDUMP=/workspace/buildroot-work/buildroot/output/host/bin/arm-buildroot-linux-uclibcgnueabi-objdump
for RANGE in "0xa1900 0xa1a80" "0xa26b0 0xa26f8" "0xa0800 0xa08c0"; do
  set -- $RANGE
  echo "=== $1 to $2 ==="
  "$OBJDUMP" -d --start-address="$1" --stop-address="$2" /stock/sdDongle
done
'
```

**Never flash this branch before the ownership issue is resolved and a recovery route is verified.** Stock wireless MMI operation remains the known-good baseline.
