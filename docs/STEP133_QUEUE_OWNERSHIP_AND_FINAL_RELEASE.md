# Step 133 — Native queue ownership and final-release ordering

**Status:** uploaded verified-stock ARM queue ownership report reviewed and archived. Normal empty→nonempty queue retain and last-work release ordering are established. Client finalizer and abnormal callback guarantee remain unproven. No runtime firmware changed.

## Scope and source identity

All native addresses below refer only to the SHA-256-verified stock AK3918AN `sdDongle`:

`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.

Step 132's uploaded and [archived ARM report](../evidence/AK3918_step132_queue_cancellation.txt) establishes the different behaviors of the queue destructor, queue dispatch worker, HTTP completion callback, and client invalidation. Step 133 examines **ownership and ordering**, not simply whether the callbacks exist.

## Known relationships from prior verified-stock excerpts

| Function / address | Observed instruction sequence | What it supports |
| --- | --- | --- |
| HTTP client constructor `0xa641c` | `bl 0xa32b0` at `0xa64a0`; `str r0,[r4,#8]` at `0xa64a4` | Constructor retrieves a process-global dispatch queue pointer, stores it at `client+0x08`, and explicitly retains the queue at `0xa64a8` |
| HTTP send `0xa6974` | `ldr r0,[r6,#8]` at `0xa6a68`; `bl 0xa1900` at `0xa6a6c` | An HTTP send with zero return *attempts* asynchronous submission to the client's queue; dispatch-node allocation failure can prevent actual insertion |
| HTTP send `0xa6a4c..0xa6a54` | Retains message and client before enqueue | Accepted work holds a retained `client` until its send-dispatch callback |
| Send-dispatch callback `0xa6040` | Appends message into client list, invokes client state machine, releases `client` at `0xa6070` | The enqueue-specific client retain is released after queue dispatch executes |
| HTTP client invalidation `0xa6584` | Retains client at `0xa658c`, enqueues invalidation via `0xa1900` at `0xa65a4` | Client invalidation is itself asynchronous and has its own client retain |
| Invalidation callback `0xa4f30` | Calls error handler and releases client at `0xa4f48` | Enqueued invalidation balances its own retain on callback execution |
| Car global client teardown `0x2a76c` | Invalidates client at `0x2a78c`, releases it at `0x2a794`, clears global at `0x2a79c` | The car-side global pointer is dropped after requesting invalidation |
| Dispatch queue destructor `0xa01b8` | Reads `queue+0x30` at `0xa0250`; diagnostic when nonempty | Destructor expects an empty work list, but does not invoke pending work callbacks |
| Normal queue drain `0xa304c` | `blx r3` for work node at `0xa308c`; free work node at `0xa3094` | A regularly dispatched node runs its function before being freed |

These are **separate client, message and queue ownership layers**. The observed native client retains do not, by themselves, establish the queue object's lifetime/refcount rules. Nor does the queue's warning on destruction establish whether normal shutdown can produce a nonempty queue.

## Step 133 ownership questions and resolution status

1. **Resolved:** `0xa32b0` retrieves a queue pointer from global dispatch state; the HTTP client explicitly retains it at `0xa64a8`.
2. **Resolved for successfully inserted work:** `dispatch_async_f` retains the queue once on the empty-to-nonempty transition at `0xa19ec`, and the worker releases that reference at `0xa30a4` after the final callback. It does not acquire one reference per node.
3. **Unresolved:** the precise HTTP-client CF finalizer's release of `client+0x08` has not been identified.
4. **Partly resolved:** queued work's own reference prevents ordinary premature queue free until dispatch completion, but the full client/global shutdown sequence and exceptional failure behavior remain unverified.
5. **Not safe to generalize:** allocation failure at `0xa1980` can prevent queue insertion with a zero HTTP send return; no mechanism has been proven to reclaim its native message/client retains or shim metadata safely. Callback delivery cannot be guaranteed in all failure states.

The Step 133 report establishes normal queue retain/release mechanics, but **not** the HTTP-client finalizer, complete process shutdown sequence, or callback delivery across allocator failure and abnormal termination.

## Read-only report generation

The new `scripts/step133_extract_queue_ownership.sh` extracts 12 targeted ranges using the existing verified-stock ARM/uClibc objdump in Docker:

| Region | Coverage |
| --- | --- |
| `0x9fff0..0xa0384` | Queue object final free and destructor |
| `0xa0384..0xa058c` | Wake and queue scheduling helpers |
| `0xa1900..0xa1b20` | Asynchronous work-node enqueue, locking and scheduling |
| `0xa3000..0xa30c0` | Serial work-node dispatch |
| `0xa3180..0xa3480` | Queue creator and queue assignment helper |
| `0xa6000..0xa65bc` | HTTP client constructor, finalizer candidates and invalidation |
| `0xa6974..0xa6a80` | Send queue pointer and enqueue call |
| `0xa4d7c..0xa4f50` | Error handler's message completion |
| `0x2a76c..0x2a7a8` | Global client invalidation/release |

The script mounts both stock analysis and Buildroot volumes **read-only**, checks the stock ELF SHA-256, verifies 12 extraction sections and four exact constructor/send ARM opcodes, and publishes a report only after those checks pass.

On the Mac:

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step133_extract_queue_ownership.sh
```

Expected output: `~/Desktop/AK3918_step133_queue_ownership.txt`.

The script does not modify firmware, generate a test archive, or operate on the dongle. Upload the resulting report for line-by-line ownership analysis.

## Local extraction — user-reported PASS

The user fast-forwarded the experimental branch from `02b7a0e` to `fc0a933a5792` and ran `bash scripts/step133_extract_queue_ownership.sh` on their Mac. The terminal output reports:

```text
PASS: verified-stock queue constructor/assignment/send callsites captured
NOTE: queue lifetime and destruction ordering still require analysis
PASS: Step 133 read-only queue ownership report at /Users/wademacintosh/Desktop/AK3918_step133_queue_ownership.txt
No executable, archive, device setting or recovery firmware changed.
```

This confirms the script's stock-SHA and expected opcode/checkpoint gates passed and its report was produced. The complete report has since been uploaded, reviewed and archived in `evidence/AK3918_step133_queue_ownership.txt`; see findings below. Its local extraction PASS alone did not establish lifetime safety. Do not equate the extractor's PASS with a safe callback cleanup or device-runtime validation.

## Completed review of uploaded Step 133 ARM report

The user uploaded a **1,411-line** report generated by the Step 133 SHA-256-gated read-only script. Its complete bytes are preserved as [Step 133 stock ARM evidence](../evidence/AK3918_step133_queue_ownership.txt) and checked against exact opcodes by `tests/test_step133_native_queue_ownership.py`.

### 1. A queue is a reference-counted object

- `0xa0454..0xa04a8`: the queue/object retain path validates the pointer then performs an atomic increment of `object+0x04` (`mov r1,#1` at `0xa0498`, atomic helper `0xf0090` at `0xa04a0`).
- `0xa04bc..0xa0560`: the release path decrements that same field by `-1` (`0xa0500`, `0xa0508`). If the count becomes zero, it invokes the destructor function pointer loaded from `object+0x0c` (`0xa0550`, `bx r3` at `0xa0560`).
- `0xa32b0..0xa3344` returns the queue pointer stored in a global `+0x24` slot after the dispatch initialization check, rather than allocating a new per-HTTP-client queue in this helper. The client's `0xa64a0` calls that getter, stores its result at `client+0x08` at `0xa64a4`, then **retains the queue explicitly** at `0xa64a8`.

This establishes an independent queue reference owned by the client. It does **not** locate the corresponding finalizer/release of `client+0x08`—the report's `0xa6510..` range includes a client creation wrapper and invalidation entry, not the definitive CF object finalizer.

### 2. Pending queue work independently holds a reference

- `dispatch_async_f` at `0xa1900` obtains a 12-byte work node with `calloc(1,12)` at `0xa1974..0xa1984`.
- After taking `queue+0x2c` mutex, it inspects `queue+0x30` at `0xa19dc`. If **empty**, it calls the queue-retain helper at `0xa19ec` before inserting the first work node at `0xa19f4..0xa19fc`. Inserting additional nodes into an already nonempty queue does not take another such reference.
- The serial dispatch worker removes a node, unlocks the queue, runs its callback at `0xa308c`, and frees the node at `0xa3094`. If the popped node was the last in its current batch, it **releases the queue reference** through `0xa30a4` (call to `0xa04bc`), *after* executing the callback.
- This establishes the intended lifetime invariant: successful empty-to-nonempty enqueue retains the queue until the corresponding work-list draining callback has run, even when a separate client-held reference is later relinquished.

The nonempty queue release is guarded by a mutex and the worker's last-node state, but not every reconnect, worker scheduling, thread failure or process-exit interleaving has been observed. Reference ownership alone does not guarantee liveness.

### 3. Zero HTTP send return is not proof of actual enqueue

**Important refinement to Steps 128/131:** the `dispatch_async_f` helper has a failed-node-allocation path.

- `0xa1980` calls `calloc`; `0xa1988` branches to insertion only when allocation succeeds.
- On allocation failure the function follows a diagnostic path (`0xa198c..0xa19c0`) then returns at `0xa19c8`, **without inserting a work node or taking the pending-work queue retain**. An invalid queue state also takes a diagnostic/return path.
- `HTTPClientSendMessage` at `0xa6a6c` calls this **void-returning** dispatcher and then assigns `r5=0` at `0xa6a70`. It cannot propagate dispatch-node allocation failure as a nonzero HTTP return. The message/client were retained before this call at `0xa6a4c/0xa6a54`.

Consequently, `http_send != 0` still proves a **pre-dispatch preparation failure** for this verified stock ELF, consistent with Step 131. But `http_send == 0` proves only that the dispatch call was attempted; the queued callback is **not guaranteed to have been inserted**. A failed allocation could strand native retains and shim ticket metadata, and neither can be safely released by guessing from the return value. Timeout-based ticket reclamation remains prohibited.

### 4. Queue final-release conclusion and limitation

The queue destructor `0xa01b8` reads `queue+0x30` at `0xa0250` and reports a nonempty pending-work list. It does not itself run node callbacks. The normal enqueue/drain reference pair (`0xa19ec`/`0xa30a4`) is the intended protection against premature final free **for successfully inserted work nodes**.

A queue destructor with pending nodes therefore indicates an abnormal ownership or scheduling path, not an opportunity for the shim to clear all canceled tickets. The precise HTTP-client CF finalizer, global queue retirement and device-runtime behavior still need independent tracing.

**Safety decision:** no `altscreen.c` changes. Preserve the existing eight-slot, callback-only tombstone reclamation; do not add timeouts, manual CF releases or assumed queue-cancellation shortcuts. Source-level GitHub checks are not flash authorization.

## Safety gate and next action

- The host test `tests/test_step133_queue_ownership.py` checks read-only mounts, syntax, required extraction regions, SHA-256 gate and exact native instruction identities. It also validates that the report verifier rejects missing/changed critical addresses and that accepted-request tombstones remain preserved.
- **No edits to `altscreen.c`** and no new feature flags are required for Step 133. The last four ARM/uClibc configurations passed on Step 131 source; running them again is unnecessary for this evidence-only change.
- Reclaim a successfully enqueued request record only once the corresponding native completion is proven, **not** merely at client invalidation, queue free, timeout or reconnect.
- The experimental combined stream-111 firmware is **not device-validated and not cleared for flashing**. `main`, historical firmware and stock recovery are unchanged.

**Next:** [Step 134 — HTTP client CF finalizer and global queue shutdown](STEP134_CLIENT_FINALIZER_AND_GLOBAL_QUEUE.md) adds a verified-stock, read-only extraction and opcode gate to locate the client's `client+0x08` release and global queue retirement ordering. This remains a pending native evidence question; no missing-callback fix is justified by the currently verified source.
