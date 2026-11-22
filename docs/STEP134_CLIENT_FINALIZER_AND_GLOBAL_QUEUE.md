# Step 134 — HTTP client CF finalizer and global queue shutdown

**Status:** Step 134 local extraction passed; although its full report remains unattached, subsequent [Steps 135–136](STEP136_HTTP_FINALIZER_CONTROL_FLOW.md) identified and disassembled the `HTTPClient` finalizer, confirming release of `client+0x08` at `0xa4b1c`. No change to runtime firmware, packaging, recovery or `main`.

## Question

Step 133 established that the client explicitly retains its dispatch queue, separately from the temporary queue reference held while an accepted work node is pending. The missing fact is **where the HTTP client's CF object finalizer releases `client+0x08`** and whether normal process-global queue retirement waits for all client-held and work-held references.

A second unresolved failure mode is the stock `dispatch_async_f` work-node allocation failure at `0xa1980`: the outer HTTP sender can return zero without an actual insertion. That must remain a fail-closed, no-timeout-reclaim state unless additional independently verified evidence proves otherwise.

## Anchors already established from stock ARM evidence

| Address | Verified observation | Interpretation |
| --- | --- | --- |
| `0xa641c` | HTTP client constructor initializes a CF object | Locate class registration and finalizer separately |
| `0xa64a4` | `str r0,[r4,#8]` | Client stores queue pointer |
| `0xa64a8` | `bl 0xa0454` | Client holds an independent queue reference |
| `0xa6584` | Retains client and attempts asynchronous invalidation | Invalidating a client is not a synchronous finalization barrier |
| `0xa19ec` | Queue retains itself on empty-to-nonempty work transition | Successfully inserted queue work holds the queue alive |
| `0xa30a4` | Queue releases last-work reference after callback | Normal callback-before-work-release ordering |
| `0xa33b4..0xa342c` | Global-queue retirement code eventually branches to queue destructor `0xa01b8` | Examine process shutdown checks and global ownership |
| `0xa1980..0xa19c8` | Work-node allocation failure can return without insertion | Zero HTTP send return does not prove a callback was enqueued |
| `0xa01b8` | Queue destructor checks for pending work | Does not itself deliver pending callbacks |

Evidence: [Step 132](../evidence/AK3918_step132_queue_cancellation.txt), [Step 133](../evidence/AK3918_step133_queue_ownership.txt) and the [Step 133 analysis](STEP133_QUEUE_OWNERSHIP_AND_FINAL_RELEASE.md). All addresses and control-flow observations are specific to the stock binary SHA-256:

`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.

## New collection: twelve disassembly ranges plus callsite hints

`scripts/step134_extract_client_finalizer.sh` performs a read-only native analysis using the existing Docker ARM objdump, after verifying the exact stock executable checksum. It extracts:

1. `0x84640..0x84720` — CF runtime class creation and registration context.
2. `0xa6364..0xa6510` — HTTP class descriptor and client queue assignment.
3. `0xa6510..0xa65d0` — client create and invalidation wrappers.
4. `0xa4f30..0xa5180` — possible client finalizer/error-handler neighbors.
5. `0xa5180..0xa5400` — HTTP state-machine and cleanup candidates.
6. `0xa6040..0xa6078` — send handoff and client release.
7. `0xa32b0..0xa3448` — process-global queue access and retirement.
8. `0xa1d80..0xa1f80` — dispatch-global initialization.
9. `0xa0454..0xa0568` — dispatch object retain and release.
10. `0xa1900..0xa1b20` — async work-node insertion and failure.
11. `0xa3040..0xa30bc` — serial callback and last-work reference release.
12. `0x2a76c..0x2a7b0` — car-side global HTTP client invalidation.
13. `0xa4d7c..0xa4f50` — error and invalidation message-list drain.

It also prints a **cross-reference hint section** for HTTP-module calls into the queue reference and dispatch helpers. These hints are **not proof of the target's register identity or a CF finalizer** until the complete relevant control flow is inspected.

The script validates fourteen sections, presence of nineteen critical ARM addresses, and exact stock opcodes for the client queue retain and the queue work release. The output is only published after those checks pass.

## Run on the Mac

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step134_extract_client_finalizer.sh
```

Expected output: `~/Desktop/AK3918_step134_client_finalizer.txt`. **Upload the report to the conversation for inspection.** No compilation, firmware packaging, flashing or dongle interaction is performed.

## User-run Step 134 extraction result (2026-11-21)

The user updated the experimental branch from `fc0a933` to `da29d1c`, and ran `bash scripts/step134_extract_client_finalizer.sh` on their Mac. Their terminal reported:

```text
PASS: stock client queue retain and global queue retirement anchors captured
NOTE: finalizer identity and shutdown guarantees require manual control-flow analysis
PASS: Step 134 read-only client finalizer report at /Users/wademacintosh/Desktop/AK3918_step134_client_finalizer.txt
No executable, archive, device setting or recovery firmware changed.
```

This establishes that the checksum-gated read-only script completed and produced a report for the source revision `da29d1c`. The GitHub host tests for the script also passed. **The full generated report has not yet been uploaded or archived in this repository**, so it cannot be used to identify the CF finalizer or certify queue shutdown ordering. The local PASS applies to instruction capture only, not callback-delivery guarantees.

**Pending evidence:** attach `~/Desktop/AK3918_step134_client_finalizer.txt` to the conversation; inspect the complete class descriptor, finalizer callsites and global shutdown branches before considering a source change.

## Validation and decision gate

`tests/test_step134_finalizer_extraction.py` checks the script's SHA-256 gate, read-only Docker mounts, shell syntax, exact anchors, and rejection of synthetic missing or altered instructions. GitHub Actions runs these tests together with the pre-existing source-safety and callback-tombstone tests. The tests cannot resolve the finalizer until the stock ARM report itself is examined.

**Do not** reclaim tracking records from `http_send == 0` based on elapsed time, HTTP client invalidation, queue release, CF finalization or global queue shutdown. A native callback can still arrive, and an unsuccessful allocation may never schedule one. The experimental stream-111 feature is unvalidated on the dongle and remains disabled for normal builds.

**Resolution through later verified evidence:** [Step 135](STEP135_CF_CLASS_DESCRIPTOR_GATE.md) decoded the `HTTPClient` `CFRuntimeClass` finalizer slot, and [Step 136](STEP136_HTTP_FINALIZER_CONTROL_FLOW.md) proved that `0xa4b08` calls `dispatch_release(client+0x08)` at `0xa4b1c`. Successful queued work retains the queue independently until its dispatch callback finishes; the finalizer does **not** itself drain HTTP messages, and allocator failures or abnormal process shutdown can still lose callbacks. No safe generic callback-reclaim barrier exists.
