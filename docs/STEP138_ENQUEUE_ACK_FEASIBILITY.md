# Step 138 — Feasibility of reliable, per-request native enqueue acknowledgments

**Status: source-only feasibility analysis and host model. No stock binary alteration, runtime shim change, native instrumentation, firmware package, target installation, or recovery modification.**

## Finding

**There is no independently verified, noninvasive, per-request enqueue acknowledgment available to the existing `shim_screen_http_send` wrapper.** A native `HTTPClientSendMessage` zero return cannot distinguish successful node insertion from a failed `dispatch_async_f` allocation. A callback eventually arriving confirms completion for that message, but it does not supply an immediate enqueue success/failure result. Recovering capacity for missing callbacks remains deliberately fail-closed.

This is a conclusion about the **stock API and observed ARM control flow** (SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`), **not** a claim that no invasive redesign could ever produce a reliable acknowledgment.

## Grounded evidence

| Boundary | Stock address | Exact behavior | Consequence |
| --- | --- | --- | --- |
| Native HTTP preparation | `0xa69c0..0xa6a00` | Nonzero prep result bypasses message/client retain and dispatch | Nonzero remains a proven, immediately reclaimable pre-dispatch failure |
| Native HTTP retains | `0xa6a4c`, `0xa6a54` | CFRetain(message), CFRetain(client) | Native ownership is acquired before node allocation and insertion |
| Dispatch attempt | `0xa6a6c` → `0xa1900` | Calls void asynchronous dispatcher | No success/failure result crosses into the HTTP sender |
| Dispatch allocation | `0xa1980` and branch `0xa1988` | `calloc(1,12)`; null falls through diagnostic and return `0xa19c8` | A dropped work node need not produce callback |
| Node publication | `0xa19ec..0xa19fc` | Work-queue retain on empty transition and link node into queue | Success is observable only *inside* native dispatch machinery |
| Forced HTTP result | `0xa6a70` | Sets `r5=0` after dispatch attempt | Zero means attempt, not confirmed publication |
| Worker | `0xa3074`, `0xa308c` | Dequeues and executes callback | Queue length can return to zero before caller samples it |
| Work-queue release | `0xa30a4` | Releases queue reference after dispatch callback | This is distinct from the HTTP message completion |
| HTTP finalizer | `0xa4b1c` | Releases `client+0x08` queue reference | Does not drain and complete all pending HTTP messages |

These facts come directly from the archived [Step 133 disassembly](../evidence/AK3918_step133_queue_ownership.txt), [Step 136 finalizer report](../evidence/AK3918_step136_http_finalizer.txt), and the [Step 137 failure-path audit](STEP137_UNOBSERVABLE_DISPATCH_FAILURE.md).

## Candidate observation mechanisms

| Candidate | Noninvasive? | Per-request correlation? | Distinguishes failed allocation vs queued work? | Assessment |
| --- | --- | --- | --- | --- |
| Native HTTP send return code | Yes | Yes, through call arguments | **No** for zero returns | Insufficient |
| Timeout / no HTTP response | Yes | Can track held ticket | **No**; scheduled callbacks may be delayed | Unsafe reclaim |
| Queue depth snapshot | Requires trusted access to native queue state, so not available through existing API | **No**; one process-global queue serves multiple work items | **No**; a successfully dequeued item and failed allocation can both show depth 0 | Not an acknowledgment |
| Queue/global reference count | Not exposed through wrapper | No per-message identity | **No**; other clients and work also own refs | Not an acknowledgment |
| Existing diagnostic/printf logs | Read-only logs may be available; no guaranteed host API | No verified request-token field | At most evidence that *some* allocation failed, not which request | Useful for diagnosis only |
| Intercepting `calloc` | **Invasive** process-wide hook; not selected | Correlation across threads and call stacks unproven | Null return alone cannot safely justify release or guarantee no future callback | No deployment proposal |
| Tracing a queue work-node pointer | **Invasive** native-data inspection or hook | Might be possible after success | Queue can drain before inspection; synchronization and node lifetime unproven | Not presently safe |
| Instrumenting the native dispatcher and HTTP sender | **Invasive** design change | Potentially, only with a true per-request identifier | Potentially **yes** if status is emitted from both the publish and drop paths, and native retain rollback is proven | Research candidate only, not authorized to patch |
| The native `msg+0x904` HTTP completion callback | Existing shim uses this | Yes, for a still-tracked pointer | Confirms actual callback only, not a timely enqueue status | **Only justified reclamation signal currently used** |

## Requirement for any *future* reliable native acknowledgment

A source-only candidate design must satisfy **all** of these conditions before any new runtime code is proposed:

1. **Identity:** correlate each receipt to the exact reserved request or generation/ticket, not just `client` address, queue depth or a global counter. The stock dispatcher only receives `queue`, `context` and a function pointer, so identity propagation must be specified and safely synchronized.
2. **Source of truth:** a positive acknowledgment must be produced only after the native queue node has been linked successfully; a negative acknowledgment must prove that no worker can later execute that submission. Recording a flag before `calloc` or before queue publication is insufficient.
3. **Native ownership:** the negative path must prove that the two native CFRetains performed before dispatch are correctly balanced. Clearing *shim metadata* alone is not a resolution for a stranded native message/client; manual CF release from the shim without proof remains unsafe.
4. **Concurrency:** an independent worker may execute the dispatch callback before a post-publication acknowledgment reaches the sender. If the HTTP completion callback also arrives before a receipt, the receipt may not resurrect the completed ticket.
5. **Cancellation:** reconnect, invalidation, finalizer and global shutdown are not acceptable negative acknowledgments unless a synchronizing no-future-callback guarantee is independently demonstrated for that specific message.
6. **Failure isolation:** on unknown status, interrupted instrumentation, partial publication, invalid queue or process failure, keep the tombstone and refuse new combined stream-111 requests when capacity is full.
7. **ABI and stock isolation:** any proposed change must be proven against the exact original stock ARM ABI, original dispatch-thread behavior, and feature-flag-off execution. Source and host models alone do not authorize an ELF patch or flashing.

**Important:** even a correct **published** acknowledgment does not mean the later HTTP response callback was delivered. The published ticket must remain tracked until that response; only a proven *dropped-and-balanced* result would potentially allow an alternative safe reclaim.

## New host test

`tests/test_step138_ack_contract.py` pins the actual stock ARM opcodes for allocator failure, node publication, native retains, return-zero behavior and queue worker dequeue, and confirms the unchanged fail-closed shim. It then runs a deterministic **source-grounded but simulated observation model**:

- A dropped `calloc` and a successfully published work node **already dequeued** both yield the same coarse snapshot: HTTP return zero, queue length zero, no HTTP completion, metadata still held. That invalidates queue-depth sampling as a definitive per-message receipt.
- Even explicit `PUBLISHED` must not free metadata before HTTP completion.
- An explicit `DROPPED` result only authorizes hypothetical reclaim when native retains have been balanced **and** no future callback can execute.
- Host event order permutations test acknowledgment-before-callback and callback-before-acknowledgment, rejecting ticket resurrection.
- The existing production shim still reclaims known nonzero preparation failures, retains zero-return metadata, and never resets canceled tracking records on teardown.

These are **test-model invariants, not observations from the physical dongle**. No native allocator fault injection or instrumented dispatcher is executed.

## Decision

**Reject** timeout cleanup, queue-depth polling, global refcount inference and log-derived ticket reclamation. **Do not add** an invasive dispatcher hook or native reference manipulations to the experimental branch without a separate validated design and runtime safety plan.

**Keep `altscreen.c` unchanged** and the eight-slot fail-closed capacity. The next useful step is a **design review of whether a native receipt can be published without changing stock dispatch semantics** and a more complete host concurrency/fault-injection model, not building or flashing the combined stream-111 experiment. For now, the safe result is documented **non-availability of a noninvasive acknowledgment**.
