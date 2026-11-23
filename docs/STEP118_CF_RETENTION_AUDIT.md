# Step 118 — CoreFoundation retention audit (partial)

Stock executable SHA-256: `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`. Read-only disassembly supplied in `AK3918_step118_cf_retention.txt`.

## Verified from the supplied instructions

- The stock array callback table at `0x134200` contains five 32-bit callback words: version zero; retain pointer `0x85bfc`; release pointer `0x85cf4`; null description; equality pointer `0x85f18`.
- `0x867a0` is only an append dispatch stub: it loads the element into `r2`, sets `r1 = -1`, and branches to `0x865b4`. The actual insertion code at `0x865b4` was *not captured*.
- `0x885f8` is the underlying dictionary insertion target of `0x836dc`. Its shown path allocates a 12-byte entry, stores it in a dictionary bucket and increments a count at `0x88768..0x88778`. The output ends at `0x8877c`, before the rest of the method. Whether the inserted array value is retained cannot yet be determined from this excerpt alone.

## Status

Step 117 established the stock function owns and later releases its stack-local array pointer. The Step 112 swap-and-release design remains consistent with that local-reference pattern; Step 118 establishes the retain/release callbacks supplied for array elements, but **does not verify their invocation** by the append implementation, or dictionary retention of the array itself.

No source correction is justified solely by these excerpts. The teardown-after-array-publish / before-HTTP-send race is independent of this ownership question and remains unresolved.

## Remaining read-only evidence

- `0x8877c..0x88850`: dictionary insertion continuation.
- `0x865b4..0x867a0`: actual array append implementation.
- `0x85bfc..0x85d90`: callback retain/release entrypoints.
- `0x82fc0..0x83030`: wrapper calling append.
- `0x84ee0..0x85000`: dictionary lookup/probe helper when needed.

**Do not package or flash.**
