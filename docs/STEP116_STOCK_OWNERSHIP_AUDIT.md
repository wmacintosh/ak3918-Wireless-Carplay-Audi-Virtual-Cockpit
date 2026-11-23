# Step 116 — stock CoreFoundation array ownership audit (partial)

Source: read-only `arm-buildroot-linux-uclibcgnueabi-objdump -d` of the stock `sdDongle` executable, verified SHA-256
`b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.

## Verified stock instructions

- `0x2fad4`: `mov r1,r5` prepares video stream 110.
- `0x2fad8`: `add r0,sp,#52` passes address of local stream-array slot.
- `0x2fadc`: `bl 0x9327c` invokes the native array-ensure helper.
- `0x9327c` checks the pointer at `r0`; when null, its path begins creating an array via `0x82e10`. The collected helper range stops before its append path (`0x93308`).
- `0x2fae0`: `ldr r2,[sp,#52]` reloads the array slot, so a replacement pointer is observable by native code.
- `0x2faec`: `bl 0x836dc` passes the array into the outgoing dictionary.
- `0x2fb90`: native code sets the response callback at message offset `0x904`.
- `0x2fba0`: stores an unrelated stock context pointer at `0x8fc`.
- `0x2fbb0`: native HTTP submission through `bl 0xa6974`.
- `0x2fb38` branches to the common later path at `0x2fde8`, **outside** the extracted report.
- `0x82c78`, the candidate release entrypoint, branches directly to `0x85c04`; the report does not include that callee's body.

## Conclusions and limitations

1. Step 112's assignment `*streams = replacement` is consistent with the actual stack-local array pointer load at `0x2fae0`. The disassembly does **not** prove ownership, correct retain counts, or safety of `cf_release(replaced_streams)`.
2. The stock function performs additional work between array insertion and HTTP submission. Concurrent teardown during that gap could leave a stream-111 entry in an outbound request even when tracking state has been canceled. The code path alone does not prove whether teardown actually executes concurrently.
3. The complete local pointer initialization and the final cleanup/release must be examined before changing reference-count behaviour.
4. The Step 115 tombstone patch addresses response association only; it does not solve (2).

## Needed read-only follow-up

Disassemble:
- `0x2e904..0x2e9c0` (function prologue / local initialization)
- `0x2fd00..0x302a0` (error paths, common cleanup, end of function)
- `0x932c0..0x93350` (array ensure append path)
- `0x85c04..0x85c60` (CFRelease implementation entry, optional)

Compare all reads and writes of `[sp,#52]` and calls to `0x82c78` within the complete function. Do not infer runtime safety from successful syntax or sanitizer tests alone.

**Status: source-only experiment; do not package or flash.**
