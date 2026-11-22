# Step 133 — Native queue ownership and final-release ordering

**Status:** read-only ownership investigation in progress. Existing stock ARM excerpts establish a construction/send path, but **do not yet establish destruction order or guarantee callback delivery on abnormal shutdown**. No experimental runtime firmware changed.

## Scope and source identity

All native addresses below refer only to the SHA-256-verified stock AK3918AN `sdDongle`:

`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.

Step 132's uploaded and [archived ARM report](../evidence/AK3918_step132_queue_cancellation.txt) establishes the different behaviors of the queue destructor, queue dispatch worker, HTTP completion callback, and client invalidation. Step 133 examines **ownership and ordering**, not simply whether the callbacks exist.

## Known relationships from prior verified-stock excerpts

| Function / address | Observed instruction sequence | What it supports |
| --- | --- | --- |
| HTTP client constructor `0xa641c` | `bl 0xa32b0` at `0xa64a0`; `str r0,[r4,#8]` at `0xa64a4` | Constructor creates/obtains a dispatch queue and stores it at `client+0x08` |
| HTTP send `0xa6974` | `ldr r0,[r6,#8]` at `0xa6a68`; `bl 0xa1900` at `0xa6a6c` | An accepted send enqueues its callback to the queue stored in the client |
| HTTP send `0xa6a4c..0xa6a54` | Retains message and client before enqueue | Accepted work holds a retained `client` until its send-dispatch callback |
| Send-dispatch callback `0xa6040` | Appends message into client list, invokes client state machine, releases `client` at `0xa6070` | The enqueue-specific client retain is released after queue dispatch executes |
| HTTP client invalidation `0xa6584` | Retains client at `0xa658c`, enqueues invalidation via `0xa1900` at `0xa65a4` | Client invalidation is itself asynchronous and has its own client retain |
| Invalidation callback `0xa4f30` | Calls error handler and releases client at `0xa4f48` | Enqueued invalidation balances its own retain on callback execution |
| Car global client teardown `0x2a76c` | Invalidates client at `0x2a78c`, releases it at `0x2a794`, clears global at `0x2a79c` | The car-side global pointer is dropped after requesting invalidation |
| Dispatch queue destructor `0xa01b8` | Reads `queue+0x30` at `0xa0250`; diagnostic when nonempty | Destructor expects an empty work list, but does not invoke pending work callbacks |
| Normal queue drain `0xa304c` | `blx r3` for work node at `0xa308c`; free work node at `0xa3094` | A regularly dispatched node runs its function before being freed |

These are **separate client, message and queue ownership layers**. The observed native client retains do not, by themselves, establish the queue object's lifetime/refcount rules. Nor does the queue's warning on destruction establish whether normal shutdown can produce a nonempty queue.

## Step 133 questions still requiring native code

1. What is created/retained by the queue helper `0xa32b0`, and what reference count does it initially own?
2. Does `dispatch_async_f` at `0xa1900` retain the queue per pending node, or does the queue stay alive through its owning HTTP client and scheduling threads?
3. Where is `client+0x08` released in the HTTP client's finalizer, and can that finalizer run while send/invalidate work is still pending?
4. Does the last client reference get released strictly after queued send and invalidation callbacks finish, or can the queue's last reference be dropped while pending nodes remain?
5. Can abnormal queue destruction orphan a retained HTTP message **without** invoking `msg+0x904`, and if so is there any observable lifecycle event suitable for a safe shim tracking cleanup?

The existing stock excerpts are insufficient to answer these conclusively. **Do not treat a queue being retained as proof of a guaranteed callback**: a missing worker, process termination or unsupported error path can still prevent callback delivery.

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

## Safety gate and next action

- The host test `tests/test_step133_queue_ownership.py` checks read-only mounts, syntax, required extraction regions, SHA-256 gate and exact native instruction identities. It also validates that the report verifier rejects missing/changed critical addresses and that accepted-request tombstones remain preserved.
- **No edits to `altscreen.c`** and no new feature flags are required for Step 133. The last four ARM/uClibc configurations passed on Step 131 source; running them again is unnecessary for this evidence-only change.
- Reclaim a successfully enqueued request record only once the corresponding native completion is proven, **not** merely at client invalidation, queue free, timeout or reconnect.
- The experimental combined stream-111 firmware is **not device-validated and not cleared for flashing**. `main`, historical firmware and stock recovery are unchanged.

**Pending:** inspect the Step 133 report for queue object refcount/finalizer relationships, then decide whether any further hardening is justified. No missing-callback fix is claimed at this stage.
