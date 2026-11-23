# Step 136 — HTTP-client CF finalizer at `0xa4b08`: queue-release control flow

**Status:** the user-uploaded, verified-stock 1,108-line disassembly has been reviewed and archived. **The HTTPClient finalizer at `0xa4b08` definitely releases the queue reference held in `client+0x08`.** Runtime callback delivery, OOM handling and abnormal process teardown are not guaranteed. No firmware or recovery source changed.

## Why the finalizer address is now actionable

The uploaded and [archived Step 135 report](../evidence/AK3918_step135_cf_class_descriptor.txt) establishes:

1. At ARM `0xa6368..0xa6370`, the class-registration function receives a PC-relative pointer to **`0x134e8c`** and calls the CF runtime class registrar.
2. The raw record is file-backed in `.data.rel.ro`, the ELF is `EXEC`, and the class record contains `0x000a4b08` at **offset `+0x10`**.
3. Under the [Apple open-source `CFRuntimeClass` layout](https://github.com/apple-oss-distributions/CF/blob/main/CFRuntime.h), the 32-bit fields are `version` at `+0`, `className` at `+4`, `init` at `+8`, `copy` at `+0xc`, and `finalize` at **`+0x10`**.
4. The record's version is zero, with no `init` or `copy` callback. The `+0x10` pointer is `0xa4b08`. The report contains no relocation entry for that record slot.
5. The record at `+0x30` starts a different descriptor and must not be mistaken for an additional callback of this class.

This makes `0xa4b08` the **strong, layout-grounded candidate** for the HTTP-client finalizer. It does **not** show that the native CF implementation calls that pointer on every exit path, nor show the finalizer's instructions yet.

## Step 136 read-only native audit

`scripts/step136_extract_http_finalizer.sh` first verifies the exact original stock AK3918AN `sdDongle` SHA-256:

`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.

It then:

- Confirms via the existing read-only ELF32 program-header reader that the five class-record words are exactly `[0, 0x10abbe, 0, 0, 0xa4b08]` and the name is a file-backed string.
- Disassembles the actual candidate's neighboring code over **`0xa4a10..0xa4c18`**, to establish its function boundary, register use, resource-release order and possible error branches.
- Includes the normal message completion and release at `0xa4c18..0xa4c64`, HTTP error drain, queue retain/release, HTTP client queue initialization, CF registrar, send handoff, serial worker and global queue shutdown.
- Extracts the class name string at `0x10abbe`, class record bytes and ELF relocations.
- Validates thirteen evidence sections and known ARM instructions before publishing the report.

The script only uses read-only Docker mounts and host Python. It does not patch, rebuild, package, install or flash anything.

## Run the next extraction on the Mac

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step136_extract_http_finalizer.sh
```

Report: `~/Desktop/AK3918_step136_http_finalizer.txt`.

The Step 134 report is not necessary for this narrower extraction; the Step 135 class record supplies the pointer. After the next report is uploaded, inspect these specific questions:

1. Does `0xa4b08` accept the native CF HTTP client pointer and read `client+0x08`?
2. Does it call the queue release function `0xa04bc`, and only once per constructor retain?
3. What state or error callbacks does it release before the queue reference, and can they reenter the client?
4. How do the car-side invalidation, pending-work queue retain and global queue destructor interact with that final release?
5. Can unsuccessful node allocation still strand a retained client/message without a callback? A zero HTTP send return does not prove insertion, as established in Step 133.

## User-run extraction result — PASS

The user fast-forwarded the experimental branch from `e87d1f2` to `e110f97` and ran `bash scripts/step136_extract_http_finalizer.sh` on their Mac. The terminal output confirmed:

```text
PASS: stock class record finalize candidate 0xa4b08 at +0x10; name=b'HTTPClient'
PASS: stock finalizer candidate instructions and queue lifecycle anchors captured
NOTE: finalizer queue release and callback lifetime require manual control-flow review
PASS: Step 136 read-only HTTP finalizer report at /Users/wademacintosh/Desktop/AK3918_step136_http_finalizer.txt
No executable, archive, device setting or recovery firmware changed.
```

This confirms the original-stock SHA-256 check, the `HTTPClient` class name and on-disk `finalize` slot candidate, and successful read-only disassembly extraction. **The full Step 136 disassembly report has not yet been uploaded or independently reviewed.** The extractor's PASS does not prove that `0xa4b08` releases `client+0x08`, that callbacks always run before queue teardown, or that a zero-return dispatch successfully enqueued a message.

**Pending:** upload `~/Desktop/AK3918_step136_http_finalizer.txt` to analyze actual finalizer instructions and release ordering. Continue to preserve callback tombstones until a matching native callback; no runtime-source change, packaging or flashing is authorized.

## Results from uploaded stock Step 136 report — completed

The 1,108-line local report is preserved as [original native Step 136 evidence](../evidence/AK3918_step136_http_finalizer.txt). The user ran the stock SHA-256 and class-record guarded extractor; the printed class name was `b'HTTPClient'`, the on-disk 32-bit `CFRuntimeClass.finalize` slot at `0x134e9c` pointed to `0xa4b08`, and the complete target function has now been examined. This is a **function-body proof**, not merely a class-data prediction.

### Finalizer control flow, exact native ARM evidence

| ARM address | Stock behavior | Interpretation |
| --- | --- | --- |
| `0xa4b08..0xa4b10` | Preserve client in `r4`, load `[r0,#0x08]` | Retrieve client-owned queue pointer |
| `0xa4b14..0xa4b18` | Check queue pointer; skip release if null | Conditional queue release |
| **`0xa4b1c`** | **`bl 0xa04bc`** | **Release exactly one client-held dispatch-queue reference** |
| `0xa4b20..0xa4b24` | Set `[client+0x08]=0` | Clear released queue pointer |
| `0xa4b28..0xa4b3c` | If `client+0x18` nonnull, `free` then clear | Free secondary heap buffer |
| `0xa4b40..0xa4b50` | If `client+0x47c` nonnull, call it with `client+0x474` | Invoke **optional external cleanup callback**, not the HTTP message completion callback |
| `0xa4b54..0xa4b90` | Diagnose nonzero `client+0x48` state | Diagnostic branch, not queue flush |
| `0xa4b94..0xa4bf0` | Check socket `client+0x44`; `close` when nonnegative; set `-1` | Close descriptor after queue release and optional cleanup callback |
| `0xa4bf4..0xa4bf8` | Return | Finalizer ends without invoking `0xa4c18` or draining pending HTTP message list |

The queue retain in the constructor at `0xa64a8` and the finalizer release at `0xa4b1c` are therefore **paired at the owner level** for this stock binary. The finalizer *releases the client's reference first*, before other heap cleanup, the `+0x47c` callback and socket close. Releasing a reference is **not an unconditional free**; whether the queue's own destructor runs at that point depends on the remaining queue refcount.

### Accepted work, HTTP response callbacks and queue retirement are distinct

- On a successful **node insertion**, the dispatch queue takes an active-work reference on empty→nonempty enqueue (`0xa19ec`; Step 133). Its serial worker invokes the work function at `0xa308c` and releases the active-work reference at `0xa30a4` **after the work callback**, independently of the client-owned queue reference.
- The HTTP send path retains a **client** before attempting submission, then on normal dispatch executes `0xa6040` and balances that retained client at `0xa6070`. Thus if the work node is successfully inserted, the intended object lifetime prevents the client finalizer from running while that work callback still owns the client. This does **not** mean the later HTTP **message completion** callback has necessarily run; the send-dispatch function first moves the message into the client's pending list.
- Enqueued client invalidation likewise retains the client and invokes the error/pending-message drain in `0xa4d7c` before releasing the client at `0xa4f48`. That is the **normal invalidation callback path**, not a global guarantee that an invalidation work node is inserted or completed.
- `0xa4b08` has **no pending-message iteration and no direct `msg+0x904` completion call**. It cannot serve as an alternative completion signal for shim ticket reclamation.
- The global queue retirement code at `0xa33b4..0xa342c` checks the global queue's refcount and may call the destructor. The queue destructor separately detects pending work and does not deliver callbacks (Step 132). No runtime/hardware validation proves all abnormal shutdown interleavings complete their work.

### Failure mode still unresolved and unchanged

`dispatch_async_f` may fail to allocate its 12-byte work node (`calloc` at `0xa1980`) and return *without inserting a callback*, while outer `HTTPClientSendMessage` returns zero. That means native message and client retains taken before submission can remain without a dispatch callback and **without a safe known release signal**. The normal finalizer ordering cannot fix that path, because the stranded client reference may prevent finalization entirely. The same asynchronous-node allocation concern applies when attempting to enqueue client invalidation.

**Conclusion:** no `altscreen.c` change is justified, no timeout or session-teardown ticket reclamation is safe, and no manual native CF release is authorized by this static analysis. Maintain the existing eight-slot capacity and callback-only tombstone reclamation, and leave the experiment disabled for normal firmware. [Step 137](STEP137_UNOBSERVABLE_DISPATCH_FAILURE.md) independently pins the dispatch allocation-drop branch and demonstrates with source-derived host negative controls why `http_send == 0` cannot authorize reclaim.

### Reproducibility

`tests/test_step136_native_finalizer.py` checks the **exact uploaded native opcodes**, the queue release / cleanup ordering, the independence of the normal dispatch worker reference, the fact that the finalizer does not call `0xa4c18`, and the existing fail-closed shim cancellation logic. The archival and tests use no dongle and do not compile or package firmware.

## Tests and safety gate

`tests/test_step136_finalizer_gate.py` pins the original uploaded class record, its on-disk finalizer candidate, absence of an observed slot relocation and the script's SHA-256/read-only contract. It verifies shell and embedded Python syntax, the ten native disassembly ranges and continuation of fail-closed callback tombstones in `altscreen.c`.

**No runtime source change is justified by the confirmed finalizer or the class record alone.** The stock dispatcher can fail an internal allocation even if the HTTP sender reports zero. Neither timeout reclamation nor a blanket session teardown reset can be justified without callback/ownership proof. The combined stream-111 experiment remains disabled for normal builds and is not authorized for device flashing.
