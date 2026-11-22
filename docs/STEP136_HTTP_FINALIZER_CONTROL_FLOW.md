# Step 136 — HTTP-client CF finalizer at `0xa4b08`: queue-release control flow

**Status:** read-only collection script and host verification added; full native disassembly is pending. **No firmware, `altscreen.c`, recovery image or device settings changed.**

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

## Tests and safety gate

`tests/test_step136_finalizer_gate.py` pins the original uploaded class record, its on-disk finalizer candidate, absence of an observed slot relocation and the script's SHA-256/read-only contract. It verifies shell and embedded Python syntax, the ten native disassembly ranges and continuation of fail-closed callback tombstones in `altscreen.c`.

**No runtime source change is justified by the class record alone.** The stock dispatcher can fail an internal allocation even if the HTTP sender reports zero. Neither timeout reclamation nor a blanket session teardown reset can be justified without callback/ownership proof. The combined stream-111 experiment remains disabled for normal builds and is not authorized for device flashing.
