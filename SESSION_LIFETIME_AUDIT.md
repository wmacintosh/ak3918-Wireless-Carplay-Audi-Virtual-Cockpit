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

## Dispatch queue findings (2026-11-20)

- `0xa0800` is **a dispatch-object allocator**, not a release function: it calls `calloc(1,132)`, initializes an object header/count, and constructs a mutex at `+0x14` (pointer published at `+0x2c`).
- `0xa1900` is **queue submission**: after validating the dispatch object it calls `calloc(1,12)`, records a work callback/context in the new node, locks the dispatch object's `+0x2c` mutex, appends the node using the `+0x34` tail pointer, and conditionally signals a queue condition variable.
- `0xa2488` is a **synchronous dispatch wrapper**. It sets up stack-local mutex and condition variable, passes a work callback and that local state to `0xa1900`, then locks the mutex and waits at `0xa26ec` (`pthread_cond_wait`) until the state byte at stack offset `+0x74` becomes nonzero. The remainder of its cleanup and the callback that signals completion still need validation.
- This demonstrates **work scheduling/serialization**, not a retain/release guarantee for the parent AirPlay session. Never use `0xa0800`, `0xa1900`, or `0xa2488` as a guessed session retain primitive.
- The unresolved hazard is the asynchronous `sink_thread` dereferencing its raw `snapshot.session` before calling the vendor command dispatcher and key derivation. Dispatch serialization cannot protect a pointer that was already freed before entry.

### Targeted follow-up

Inspect `0xa26f0–0xa275c` and the implementation of the callback passed through the literal loaded at `0xa26b0` to establish how the synchronous waiter is signalled and whether a dispatcher reference is retained. Then trace parent-session allocation/destruction separately.

## Wait and signaling follow-up (2026-11-20)

- The `0xa2488` wrapper calls `pthread_cond_wait` at `0xa26ec` and loops to retest a stack-local completion flag at `0xa26d8`. This is clear synchronous waiting, but does not establish the callback that sets the flag.
- `0xa18d8` performs two calls through internal dispatch-related functions (`0x8f564`, `0x8f078`); it is **not yet identified** as the waiter completion callback.
- `0xa1aa0–0xa1b1c` checks dispatch queue state and exits via an unlock path. It does not independently prove the requested callback has executed or retained the parent session.
- The argument at `0xa26b8–0xa26cc` is a function pointer loaded from a global table (`r7` base plus the literal offset `0x918`); resolve its actual callback target before attributing completion semantics.
- The parent CarPlay session remains *unretained*. No evidence supports installing a guessed release or retain hook, and no on-dongle test is authorized.

## Dispatch callback lookup target (2026-11-20)

The `0xa2488` wrapper loads a PIC/GOT base into `r7`. The PC-relative base calculation at `0xa249c` yields `0x136000`; the literal at `0xa2758` has value `0x918`. Consequently `0xa26b8` reads the function pointer from **`0x136918`**, subsequently passing it in `r2` to `0xa1900` at `0xa26cc`. This is the strongest current candidate for the synchronous completion callback. The stock image's `.got` bytes at `0x136918` are `1c fb 09 00` (little-endian), giving the concrete callback address **`0x0009fb1c`**. `readelf -rW` showed no relocation for this slot. Disassemble `0x9fb1c` to identify its behavior; its address does not establish any retain of the parent CarPlay session.

## Resolved synchronous completion callback (2026-11-20)

The `0x136918` GOT slot contains `0x0009fb1c`, an exported symbol named **`__dispatch_sync_callback`**. The disassembly confirms:
- `0x9fb20–0x9fb2c`: fetch a work-function pointer from callback context `+0` and its argument from `+4`; call the work function via `blx r3`.
- `0x9fb30–0x9fb34`: lock the caller-provided mutex from callback context `+0x20`.
- `0x9fb38–0x9fb3c`: set the caller's done flag at callback context `+0x5c` to 1.
- `0x9fb40–0x9fb44`: signal caller-provided condition variable at callback context `+0x58`.
- `0x9fb48–0x9fb50`: unlock the mutex.
- `0xa26cc` submits this wrapper to the queue. `0xa26ec` blocks on the condition until completion. Thus the synchronous dispatch mechanism and completion callback are understood.
- **Crucial:** This does not imply session retention. It only guarantees execution completion *after* the dispatcher is entered with valid inputs. The existing `sink_thread` may access a freed vendor session before calling the dispatcher. Do not treat queue serialization as an ownership solution.

## Key derivation relocation audit (source-level, 2026-11-20)

Verified in `altscreen.c` (last executable revision `82613bf`):
- `get_stream_keys` is called at sink-thread line 444 with `session+0x3ec`, a stream connection ID and a 32-byte output buffer.
- Legacy `derive_screen` at line 454 uses `session+0x200`, stream connection ID and 16-byte key/IV outputs.
- `showUI` at line 424 and `forceKeyFrame` at line 551 are also invoked from the asynchronous sink thread using the raw vendor session pointer.
- The hook calls original SETUP at line 709. A safe redesign would obtain any required key material **inside that synchronous handler**, then pass owned key bytes plus stream generation to the sink thread; do not attempt this before confirming the vendor key APIs are valid there.
- Moving keys alone does not fix the two asynchronous session-command calls. They must be removed, moved to a proven session lifetime window, or protected by a verified firmware-owned retain/teardown mechanism. Dropping them unconditionally could impair video startup/recovery.

Read-only disassembly targets: `get_stream_keys` at `0x654c0`, `derive_screen` at `0x73e84`, and tail of the original SETUP handler at `0x6a60c`. Check whether the APIs require state populated *after* SETUP and whether they access the parent session outside the supplied subobject pointer.

## Key derivation disassembly findings (2026-11-20)

- `0x654c0` begins by loading `[r0]` into `r4` (`0x654c4`), where the hook currently supplies `session+0x3ec`. A null PairVerify object changes control flow. Subsequent calls and the return status must be established before presuming successful derivation after SETUP.
- `0x73e84` constructs two connection-specific temporary strings with `asprintf`, then calls `0x73d9c` at `0x73f10`. It clears and frees those temporary strings afterward. The helper's input/output semantics and any session dependencies still require inspection.
- The original SETUP function at `0x6a60c` is long; the inspected first `0x184` bytes show early input handling and state checks, not the exact point where PairVerify state is guaranteed ready.
- A viable design must allocate immutable owned key/IV material within synchronous SETUP **only if** both derivation variants are verified available there, then remove *all* asynchronous dereferences of `snapshot.session` and safely address the `showUI`/`forceKeyFrame` dependency.
- Do not move key derivation yet: doing so based only on these entry sequences risks deriving from missing or incomplete PairVerify state.

## Key helper confirmation (2026-11-20)

- `0x73d9c` is a deterministic-looking helper for deriving 16-byte output material. It builds an intermediate state on the stack through functions `0xc6028`, `0xc60e8`, `0xc61ac`, then copies **16 bytes** to each nonnull output buffer (`0x73e00–0x73e0c` and `0x73e50–0x73e5c`). It clears 64 bytes of stack scratch before returning. This establishes output-buffer ownership and local scratch cleanup, **not** that calling it after SETUP is always safe. Verify its input-key lifetime.
- `0x654c0` dereferences the pointer supplied in `r0` immediately; the existing hook passes `session+0x3ec` and must not call it if the parent session can already be released. If the PairVerify pointer is null, its branch reaches an error/log path before the exit at `0x65658`. Success and missing-state codes remain to be interpreted.
- Key derivation is not yet relocated. Need a firmware-derived guarantee that PairVerify state and the legacy secret are initialized by the end of the synchronous SETUP handler, plus a safe way to eliminate asynchronous `showUI` and `forceKeyFrame` dispatch.

## PairVerify setter, cleanup and SETUP callsite confirmed (2026-11-20)

- `0x672f0–0x67324` is the setter for the object stored at session `+0x3ec`. It retains a non-null incoming pointer through `0x82c74`, replaces the old pointer, and releases the old pointer through `0x82c78`. This proves **PairVerify object** ownership semantics, not parent-session retention.
- `0x61254–0x61290` is a session-cleanup routine that sends an operation through session command channel `+0x3d0`, releases the PairVerify object through `0x82c78`, and clears `+0x3ec`.
- The original SETUP handler at `0x6afdc` explicitly tests PairVerify pointer availability; at `0x6b068–0x6b094` it checks that pointer and the connection ID then invokes `get_stream_keys` (`0x654c0`) on `session+0x3ec`. This **proves the firmware calls modern key derivation during SETUP** for qualifying requests, rather than requiring the later asynchronous sink thread.
- Important limit: `shim_session_setup` filters stream type 111 from the request **before** calling original SETUP. Thus the vendor's derivation at `0x6b094` might pertain to another retained stream/connection ID, not automatically type 111's `conn111`. The hook needs a separate, guarded derivation for type 111 with its own ID, and must respect unsupported/not-ready cases.
- Executable source currently leaves the raw parent `session` in `sink_args`, and asynchronously calls `send_phone_cmd` for showUI/forceKeyFrame. The known CF retain API for PairVerify is **not** a license to retain the parent session the same way.
- Before implementing even a compile-only patch, inspect the original SETUP's derivation result handling (`0x6b098–0x6b190`), and identify a safe, non-session command mechanism or an explicit session lifecycle guard for delayed commands. For a safe production path, no async parent-session dereferences may remain.

## Original SETUP key-success handling (2026-11-20)

- At `0x6b068–0x6b094`, the stock SETUP checks that the PairVerify pointer is non-null and passes the connection ID plus `session+0x3ec` into `get_stream_keys`.
- At `0x6b098–0x6b0a4`, it tests the returned status against zero. A nonzero result branches away to `0x6c334`, while a zero result continues at `0x6b0d8`.
- On the success path `0x6b0d8–0x6b0f8`, it clears an eight-byte session field at `+0x980`, copies **32 bytes** from the local key buffer to session `+0x960`, and sets a ready byte at `+0x870` to one.
- This demonstrates synchronous derivation, status checking and caller-owned key copying as a stock SETUP pattern. It does **not** establish that the alternate stream's connection ID is processed by stock SETUP (the hook filters it), or that the key material can be obtained after a failed SETUP. It does not fix the asynchronous session command calls.
- Safe target design: derive independently for saved type-111 connID while inside a verified live synchronous setup context, put derived bytes directly into a heap-owned per-stream `sink_args` snapshot, wipe intermediate buffers and never read `session+0x3ec` from the sink thread. Only implement after reviewing how modern and legacy key modes are selected and how the asynchronous `showUI`/`forceKeyFrame` functions can be made session-safe.

## Compile-only key snapshot implementation (2026-11-20)

Source changes in `altscreen.c`, commits `b282bca` and `5b85cb6`:
- Introduces `struct sink_keys` and snapshots modern 32-byte stream keys or legacy 16-byte key/IV during `shim_session_setup` after successful original SETUP, using saved type-111 connection ID.
- Refuses to advertise an alternate stream if there is no connection ID or the modern key derivation fails. The legacy helper is assumed to return generated material (its signature returns void); the code cannot directly verify legacy success.
- `sink_args` carries only the owned key material and generation, **not the vendor parent-session pointer**. The sink thread no longer reads session `+0x3ec` or `+0x200`.
- Removes all sink-thread invocations of `send_phone_cmd` for `showUI` and `forceKeyFrame`: they are intentionally **disabled**, not safely replaced. This may prevent video startup or IDR recovery. Key and IV buffers are wiped from heap snapshots and ordinary sink exit paths.
- Remaining caveats: the SETUP hook's own parent-session access is not proven immune to concurrent firmware teardown; the cluster request/callback lifetime is separately unresolved; there is no device execution or successful compilation of this source change yet. **Do not flash**.
- Next check: compile via existing Buildroot Docker with the experimental branch, then inspect exported symbols and cross-thread session accesses; do not invoke any firmware upload or flashing helper.

## Build validation and remaining hazards (user build, 2026-11-20)

The user fetched branch head `f187606` and built `libSdH-lifecycle-test.so` using the pinned Buildroot ARM/uClibc Docker compiler. The build script reported: **`PASS: ELF32 ARM, soft float, uClibc dependency, constructor, exported hook`**. This is compile/ELF validation only: no dongle upload, runtime, wireless stream test, or teardown stress test.

Additional source inspection:
- `sink_thread` no longer holds `snapshot.session`, and its frame loop checks generation without dereferencing the parent vendor session.
- `open_alt_sink` still reads `session+0x8c` in the synchronous SETUP call path and uses generation/pointer equality. The source does not prove concurrent teardown cannot happen while SETUP runs.
- `g_session_generation` increments only when `g_session != session`; pointer reuse or same-pointer reinitialization can escape logical invalidation. A generation check is not a retain.
- `showUI` and `forceKeyFrame` are disabled. The handset may not start producing video or supply an IDR without them, so **build success is not feature success**.
- The legacy `derive_screen` function returns void; there is no proven error result. Modern `get_stream_keys` has a checked status but stream IDs/state still require runtime verification.
- `build_hook.py` validates format/ABI, SONAME, constructor and exported hook only. It does **not** validate vendor absolute-function signatures, session lifetime or screen behavior.

Next gate: perform read-only build-artifact inspection (`readelf`, `objdump`, `nm`), and tighten warnings on an isolated local build, before considering controlled device testing. **Do not flash this branch.**

## Read-only ELF validation of compile-only hook (2026-11-20)

The user inspected the locally built `libSdH-lifecycle-test.so`:
- `ELF32`, `ARM`, `Version5 EABI`, **soft-float ABI** (`Flags: 0x5000200`).
- `NEEDED: libc.so.0`, `SONAME: libSdH.so`, `INIT_ARRAY: 0x5e60`, `INIT_ARRAYSZ: 8`.
- `shim_session_setup` exported as a global function at relative VA `0x1c64`; `sink_thread` present as a local function at `0x2904`.
- No dynamic `TEXTREL` entry was reported.
- Library size **27,024 bytes**.
- `snapshot_alt_keys` does not show as a separately named function, consistent with optimization/inlining but not a proof of execution behavior.
- These checks do not verify invocation arguments for vendor functions, key correctness, absence of runtime UAF, or that the phone supplies video without deferred commands. **Do not flash**.

## Command entry and teardown ordering (2026-11-20)

New read-only disassembly:
- `0x673e0` reads session readiness byte `+0x3ce`, returning the error literal at `0x67418` if zero. On the ready path it reads the dispatch object from session `+0x3d0` and calls synchronous `0xa2488` with a stack callback record.
- `0x6777c` submits a synchronous operation via the session dispatch queue, then `0x67788` calls `0x61254`. That cleanup routine itself submits an operation to the same queue at `0x61274` before releasing/clearing PairVerify `+0x3ec` at `0x61288–0x61290`.
- A separate cleanup path at `0x66bc8–0x66bdc` reads `+0x3d0`, calls `0xa04bc` and zeros that field. `0xa04bc` is labeled with a dispatch-semaphore symbol but its exact queue shutdown/retention semantics still require verification.
- **Concurrency limitation**: internal synchronous queue dispatch does not protect an outside thread's *entry* through a raw session pointer. The ready flag is not an ownership token and may be stale; even `+0x3d0` can be freed during teardown. No permission to reinstate `send_phone_cmd` on the sink thread. The local compile-only branch leaves both delayed commands disabled.

Next read-only target: inspect caller-side guard and queue release mechanics of `0xa04bc` and the broader routine around `0x66b70`, plus the parent session allocator/free references, to establish an exclusion or retention contract. Do not flash.

## Dispatch release-object refcount evidence (2026-11-20)

User read-only disassembly:
- `0xa04bc` handles a null object separately; non-null release at `0xa0500–0xa050c` calls `0xf0090` with `r0 = object+4`, `r1 = -1`, then branches on the return result. This is consistent with a decrement-and-test of a reference counter but the atomic helper's exact operation is unverified.
- On the successful decrement path `0xa0514–0xa051c` the implementation checks `object+0x0c`; the actual destructor/queue wait behavior lies beyond the requested stop address `0xa0530`.
- Session teardown at `0x66bc8–0x66bdc` invokes `0xa04bc` on `session+0x3d0` and nulls that field; other teardown code `0x67780–0x67788` synchronously dispatches through the queue before session cleanup.
- **Unresolved:** a reference count for a *dispatch object* does not grant ownership of the parent session or make it safe to read its `+0x3d0` field from a detached thread. A preexisting valid reference is required before any decrement or enqueue. Continue leaving asynchronous `showUI` and `forceKeyFrame` disabled. The earlier zsh parse error was followed by a successful Docker command and is unrelated to ELF behavior.

Next read-only work: inspect `0xa04bc–0xa0590` and `0xf0090–0xf0110` to prove the release helper's semantics and whether it can free a queue with outstanding synchronous callers. Then inspect the complete teardown/entry coordination; do not flash.

## Atomic dispatch reference counting confirmed (2026-11-20)

- `0xf0090` is a CAS-retry atomic-add helper: reads `[r0]`, adds the delta from `r1`, calls the target held in `r6`, retries while the return indicates failure, and returns the new value. The literal loaded at `0xf00c4` is `0xffff0fc0`, the ARM Linux userspace cmpxchg helper address.
- At `0xa0500–0xa050c`, `0xa04bc` calls `0xf0090(object+4,-1)` to decrement the dispatch object's reference count. It returns if the new count is nonzero. At zero, `0xa0514–0xa0560` reads the function pointer at `object+0x0c` and tail-calls it as a destructor, with a diagnostic path for null destructor pointers.
- The dispatcher is therefore **reference-counted**, but this does not establish thread-safe acquisition of a reference from a session-owned pointer or queue shutdown/drain semantics. Never call `f0090` with a borrowed pointer whose memory may already be freed; incrementing after destruction is a use-after-free.
- Existing compile-only hook continues to exclude `session` from asynchronous sink arguments and disables delayed `showUI`/`forceKeyFrame` commands.
- Next target: inspect where `object+0x0c` destructor pointers are installed (queue constructor near `0xa0800`) and inspect the target destructor's behavior, especially outstanding work handling and worker-thread shutdown. Do not flash.

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

1. Which callback signals completion of the synchronous `0xa2488` wait, and does any command dispatch mechanism retain its **parent session** (rather than just the dispatch queue)?
2. Which function actually frees the dispatch object allocated by `0xa0800`, and can that overlap with a new command?
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
