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
| `0xA6A6C` | `bl 0xA1900` | Enqueue message and callback `0xA6040` |
| `0xA6A70` | `mov r5, #0` | Enqueued path forces successful return |
| `0xA6A74` | `mov r0, r5` | The common return carries either preparation error or zero |
| `0xA6A7C` | `pop {r4,r5,r6,r7,pc}` | Function exit |

**Conclusion:** in this verified stock function, `http_send(client,msg) != 0` proves the message was not enqueued and its response callback cannot subsequently be invoked by this submission. There is no other shown return path. A return of zero establishes **enqueue**, not delivery or successful video negotiation. Retained objects on accepted requests still belong to the native queue's completion/error paths and must not be reclaimed by the shim early.

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

## Remaining limits

1. This source change has **not** been compiled for ARM/uClibc on the user's Mac after Step 130; repeat `scripts/step129_validate_arm_matrix.sh` when preparing to validate this revised source.
2. The work remains version-specific. Do not infer the same error/queue contract for firmware with a different SHA-256.
3. Enqueued requests that never receive a callback can **still** occupy their tombstone record indefinitely. Automatic reclamation on timeout or session teardown would be unsafe without a proven native callback-cancellation/lifetime guarantee. This is intentionally fail-closed.
4. The parent vendor receiver-session lifetime and reconnect behavior remain separate on-device validation concerns.
5. The current experimental combined stream-111 firmware remains **not cleared for flashing**; normal firmware, stock recovery and `main` are unchanged.
