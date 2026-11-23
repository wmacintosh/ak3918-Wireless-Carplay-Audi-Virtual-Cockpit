# Step 135 — Locate the HTTP-client Core Foundation class descriptor

**Status:** verified-stock class descriptor report uploaded, inspected and archived. Its `HTTPClient` finalizer pointer at **`0xa4b08`** and queue-release behavior were subsequently confirmed by uploaded [Step 136 ARM evidence](../evidence/AK3918_step136_http_finalizer.txt). No runtime source or firmware changed.

## Why this follows Step 134

The user successfully ran `scripts/step134_extract_client_finalizer.sh` on their Mac, but its resulting `AK3918_step134_client_finalizer.txt` report has not been attached for detailed analysis. The archived [Step 133 stock ARM disassembly](../evidence/AK3918_step133_queue_ownership.txt) independently exposes a more precise lead: the code that registers the HTTP client's CF runtime class.

We can therefore narrow the next read-only scan to **one candidate class-record address**, rather than claiming that routine addresses in the broader Step 134 extract are already identified as CF finalizers.

## Verified native ARM call sequence

In the exact SHA-256-gated stock executable `sdDongle` (`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`):

| Stock location | Native instruction | Evidentiary meaning |
| --- | --- | --- |
| `0xa6364` | Function start | Candidate HTTP CF class registration initializer |
| `0xa6368` | `ldr r0,[pc,#84]` | Reads PC-relative literal at `0xa63c4` |
| `0xa63c4` | `0x0008eb18` | Little-endian ARM literal displacement |
| `0xa636c` | `add r0,pc,r0` | PC is `0xa6374`; class-data candidate is `0xa6374 + 0x8eb18 = 0x134e8c` |
| `0xa6370` | `bl 0x84660` | Passes the candidate pointer to the runtime class-registration routine |
| `0xa6380` | `str r0,[r3]` | Stores the returned runtime type identifier in a global slot |
| `0xa63d8..0xa6400` | Once-initializer helper calling `0xa6364` | Connects the class-registration initializer to client allocation |
| `0xa6428` | `bl 0xa63d8` | Client creation obtains the registered type |
| `0xa6440` | `bl 0x846a4` | Client instance allocation |
| `0xa64a4..0xa64a8` | Save queue to `client+0x08`, then `dispatch_retain` | The queue reference whose finalizer release remains unlocated |

The address calculation and instructions above are independently pinned by `tests/test_step135_class_descriptor.py` against the archived Step 133 report. **The candidate record's bytes, callback layout, and runtime relocations have not yet been inspected**; its finalizer must not be guessed from a nominal offset alone.

## Read-only extraction

`scripts/step135_extract_cf_class_descriptor.sh`:

- Verifies the unchanged stock executable SHA-256 and mounts the stock filesystem and cross-toolchain Docker volume **read-only**.
- Re-disassembles `0xa6364..0xa641c` and the HTTP-client's queue-retain path; verifies six critical native ARM instruction encodings.
- Lists ELF section/program-header mappings and relocations near the candidate `0x134e8c`.
- Dumps raw bytes in that address range through ARM objdump.
- Uses `scripts/step135_decode_cf_descriptor.py` to decode the **file-backed, unrelocated** ELF32 ARM little-endian words via program headers; it reports NOBITS/unmapped ranges rather than inventing missing class data.
- Treats any 32-bit word at the potential finalize slot as a **candidate only**, not proof of callback identity. The finalizer identity requires the exact runtime class layout and any applicable relocation to be established.

To run:

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step135_extract_cf_class_descriptor.sh
```

Output: `~/Desktop/AK3918_step135_cf_class_descriptor.txt`.

**Evidence requested for the next review:** upload the new Step 135 file. The earlier Step 134 report would also help relate a callback candidate to its surrounding native code, but is not required to run Step 135.

## Local Mac verification — user-reported PASS

The user fast-forwarded `wip/ak3918-step115-callback-tombstones` from `da29d1c` to `e87d1f236a0a5a7b153328ad4f0c29e915b9139c` and ran:

```bash
bash scripts/step135_extract_cf_class_descriptor.sh
```

The exact terminal result was:

```text
PASS: exact ARM class registration instructions and 0x134e8c candidate
PASS: Step 135 verified-stock read-only class record report at /Users/wademacintosh/Desktop/AK3918_step135_cf_class_descriptor.txt
NOTE: candidate finalizer identity and release order require manual analysis.
No executable, archive, device setting or recovery firmware changed.
```

This validates the script's exact-stock checksum and registration-address checks, and that it generated its report. The report's full class-record content **has not been attached to this conversation or archived in GitHub**. Neither finalizer identity nor queue destruction order can be inferred from the PASS messages alone.

**Awaiting:** upload `AK3918_step135_cf_class_descriptor.txt` to inspect the candidate class record, relocations, and finalizer function. The earlier `AK3918_step134_client_finalizer.txt` is additional useful evidence if available.

## Step 135 uploaded evidence — reviewed

The user uploaded `AK3918_step135_cf_class_descriptor.txt`, a 321-line report from the SHA-256-gated original stock ELF. It is now preserved as [Step 135 native evidence](../evidence/AK3918_step135_cf_class_descriptor.txt).

### Original class record at `0x134e8c`

| Offset | File-backed value | Meaning under 32-bit `CFRuntimeClass` layout |
| --- | --- | --- |
| `+0x00` | `0x00000000` | Class version zero |
| `+0x04` | `0x0010abbe` | Class name string pointer |
| `+0x08` | `0x00000000` | No init callback |
| `+0x0c` | `0x00000000` | No copy callback |
| **`+0x10`** | **`0x000a4b08`** | **Finalizer function pointer candidate** |
| `+0x14..+0x2c` | all zero | No other callback pointers in this descriptor |

The record is **file-backed**, inside `.data.rel.ro` (`0x134000..0x135ec8`), and the ELF is `EXEC`, not a shared-object PIE. The report prints the complete 13-entry `.rel.dyn` list and the relevant filtered `.rel.plt` entries; no relocation at `0x134e9c` appears in the captured report. This supports interpreting `0xa4b08` as the on-disk function pointer, but is not a runtime stack trace.

The `CFRuntimeClass` ABI in the [Apple open-source CFRuntime header](https://github.com/apple-oss-distributions/CF/blob/main/CFRuntime.h) declares `version`, `className`, `init`, `copy`, then `finalize`. In 32-bit ARM, that means the finalize slot is offset `0x10`. **The original firmware's runtime at `0x84660` must still be correlated with this ABI; the function at `0xa4b08` has not been disassembled as part of this uploaded report.**

The following words at `+0x30` (`0x10ad10`) and `+0x3c` (`0xa6cc0`) belong to a **neighboring class descriptor**, not callbacks belonging to this HTTP-client record.

### Decision

The file identifies a much narrower target: `0xa4b08`. That is **not** yet evidence that the HTTP client's queue retain at `0xa64a8` is eventually released in this finalizer, nor that all queued callbacks run first. The missing-HTTP-callback / `dispatch_async_f` allocation-failure issue remains open. Retain the existing fail-closed request tracking.

**Next:** [Step 136 read-only finalizer disassembly](STEP136_HTTP_FINALIZER_CONTROL_FLOW.md) targets `0xa4b08`, the CF class name, the queue-release helper and the normal global teardown path.

## Validation and safety scope

`tests/test_step135_class_descriptor.py` confirms the source-derived PC-relative address calculation, read-only mounts, pinned native callsite opcodes, ELF32 file-backed VMA extraction, and fail-closed handling of malformed ELF, wrong architecture, and NOBITS data. Existing CI continues checking source syntax, callback lifecycle, queue ownership, and experimental packaging vetoes.

No `altscreen.c` or `build_hook.py` modifications are authorized by this evidence. The caller's `http_send == 0` still cannot prove queue-node insertion (Step 133 identified internal `calloc` failure), and neither CF finalization nor process shutdown has been established as a reliable cancellation barrier. **Do not erase callback tombstones or manually release retained native objects by inference**. This work does not authorize flashing the experimental stream-111 firmware.

**Subsequent resolution:** Step 136 disassembled `0xa4b08` and directly observed `ldr r0,[client,#8]` at `0xa4b10`, `bl 0xa04bc` at `0xa4b1c`, and `str 0,[client,#8]` at `0xa4b24`. The client-owned queue reference is released first; this still **does not** prove every HTTP message receives its completion callback.
