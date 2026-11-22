# Step 131 — Native HTTP send error contract and safe request-slot reclamation

**Status: verified-stock static evidence + experimental host tests. No firmware installation or device-runtime validation.**

## Exact ARM source

The stock `sdDongle` ARM disassembly is from the user's previous verified-stock extraction, SHA-256
`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.
These addresses refer to **that AK3918AN binary only**, not OMKE's MIPS AX1800M or another Suding release.

The stock native `HTTPClientSendMessage` implementation starts at `0xA6974`.

| Address | Instruction/operation | Relevance |
| --- | --- | --- |
| `0xA698C` | `beq 0xA6A44` if `message+0x410` is null | This branch still follows the normal enqueue-success path |
| `0xA69BC` | `bl 0xA9898` | Request preparation (only when message field is nonnull) |
| `0xA69C0` | `subs r5, r0, #0` | Save preparation status and test for zero |
| `0xA69C4` | `beq 0xA6A04` | Only a **zero** preparation status continues to enqueue |
| `0xA6A00` | `b 0xA6A74` | Nonzero failure jumps to common return **before** retain or queue operations |
| `0xA6A4C` | `bl 0x82C74` | `CFRetain(message)` |
| `0xA6A54` | `bl 0x82C74` | `CFRetain(client)` |
| `0xA6A6C` | `bl 0xA1900` | Attempt asynchronous work-node insertion for callback `0xA6040`; internal allocation can fail without returning an error |
| `0xA6A70` | `mov r5, #0` | After the dispatch attempt, the HTTP sender forces zero return regardless of node insertion success |
| `0xA6A74` | `mov r0, r5` | The common return carries either preparation error or zero |
| `0xA6A7C` | `pop {r4,r5,r6,r7,pc}` | Function exit |

**Conclusion:** in this verified stock function, `http_send(client,msg) != 0` proves the message was not enqueued and its response callback cannot subsequently be invoked by this submission. There is no other shown return path. A return of zero establishes **an attempted dispatch**, not necessarily a successful node insertion, callback delivery or video negotiation. Retained objects on accepted requests still belong to the native queue's completion/error paths and must not be reclaimed by the shim early.

## Step 133 clarification — return zero can still fail to enqueue

A later verified-stock disassembly ([Step 133](STEP133_QUEUE_OWNERSHIP_AND_FINAL_RELEASE.md)) includes the body of native `dispatch_async_f` at `0xa1900`. It allocates a 12-byte work node with `calloc(1,12)` at `0xa1980`. An allocation failure takes a diagnostic/return path at `0xa198c..0xa19c8` **without queueing a callback**. The enclosing `HTTPClientSendMessage` ignores any such internal failure (the dispatcher has no error return) and still sets `r5=0` at `0xa6a70`.

Therefore, the Step 131 proof still justifies immediate reclaim only on **nonzero** preparation-error returns, before retain/dispatch. A zero return is **not sufficient proof of successful queue insertion**. The shim must continue retaining that ticket until a matching native callback, even if one never arrives. Step 131's source fix and 24-failure regression are unchanged; this is a documentation clarification backed by new static evidence.

## Source change

`combo_send_leave_locked(rc,gen,ticket)` now calls
`combo_forget_never_submitted_locked(ticket)` on `rc != 0`, then clears the active combined attempt and decrements `g_combo_send_inflight`. The helper first marks the ticket canceled and then clears only the exact matching ticket, all while holding `g_state_lock`.

The existing `client == NULL` wrapper preflight still reclaims its record without calling native send. **For `rc == 0`, nothing changes:** retain the request record until `shim_screen_response(msg)` and always delegate to the original stock response callback. Session transitions still invalidate old generation records but retain callback tombstones for **successfully enqueued** requests until callback.

This addresses repeated, verifiably pre-enqueue failures exhausting the eight-slot tracking table, without discarding tracking for any possibly queued request.

## Regression and evidence recheck

- `tests/run_step129_integrated_lifecycle.py`: compiles the real send and teardown wrapper bodies against host stubs, simulates **24 consecutive nonzero native returns** and asserts no request slots remain occupied and no send admissions remain active.
- `tests/run_step128_admission_gate.py`: asserts a nonzero return clears its record, in-flight generation and send-admission counter.
- `scripts/step131_verify_http_return.py`: validates exact opcode identities and control-flow ordering from stock objdump; rejects altered or absent critical instructions.
- `tests/test_step131_http_return.py`: positive and negative opcode tests plus read-only extraction shell syntax/mount checks.
- CI runs the above host tests and all existing stock-isolation, session-lifetime and package-veto checks.

The read-only local extraction is optional but provides an independent repeat against the exact stock executable:

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step131_extract_http_return.sh
```

Output: `~/Desktop/AK3918_step131_http_return.txt`. The script checks the original ELF SHA-256, disassembles `0xA6974..0xA6A80` with the existing Docker toolchain and runs the exact-instruction verifier **before** publishing the report. It does not compile, patch, package or flash firmware.

## Local verification — 2026-11-21

After fast-forwarding the WIP branch from `6d14d60` to commit `263596b5d1c0bdc401a06b09197dd0a4b8cf9032`, the user ran both read-only validation scripts on their Mac:

- `bash scripts/step131_extract_http_return.sh` — **PASS**. The script confirmed that the verified stock ARM nonzero-return branch exits before both reference retains and dispatch, and that an attempted dispatch forces a zero return. The report was saved to `~/Desktop/AK3918_step131_http_return.txt`.
- `bash scripts/step129_validate_arm_matrix.sh` — **PASS** for all four configurations: combined/phone `0/0`, `0/1`, `1/0`, and `1/1`.
- The terminal output explicitly reported no modifications to firmware, recovery binaries, or tar archives.
- GitHub Actions [run 44977899396](https://github.com/wmacintosh/ak3918-Wireless-Carplay-Audi-Virtual-Cockpit/actions/runs/44977899396) passed the source-level tests at the same commit.

These are user-reported local results plus an independently verified GitHub Actions result. They establish source-level cross-compilation and exact-stock opcode consistency, **not** a working wireless Virtual Cockpit display, device-runtime safety, or flash readiness.

## Remaining limits

1. The Step 131 source **has** passed all four local ARM/uClibc compile/ELF checks on the tested commit. The final patched executable, runtime hooks, live CarPlay negotiation and device behaviour still require separate verification.
2. The work remains version-specific. Do not infer the same error/queue contract for firmware with a different SHA-256.
3. Enqueued requests that never receive a callback can **still** occupy their tombstone record indefinitely. Automatic reclamation on timeout or session teardown would be unsafe without a proven native callback-cancellation/lifetime guarantee. This is intentionally fail-closed.
4. The parent vendor receiver-session lifetime and reconnect behavior remain separate on-device validation concerns.
5. The current experimental combined stream-111 firmware remains **not cleared for flashing**; normal firmware, stock recovery and `main` are unchanged.
