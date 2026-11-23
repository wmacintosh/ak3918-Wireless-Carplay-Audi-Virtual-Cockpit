# Step 115 — callback tombstones (experimental, source-only)

Based on repair branch commit `1857999b01364f7e22a4d5455f4631b7ea09f6ec`.

## Changes

- Keep a canceled entry for each instrumented HTTP message across session teardown until its callback runs; do not reset the table at session transitions.
- Reject registering a new instrumented message at an address still owned by any tracked record, including a canceled record.
- Assign unique, monotonically increasing request tickets to ensure a failed `http_send` cannot cancel a newer request simply because its pointer was reused.
- Inspect and consume the matching record **before** reading the response body; only parse stream-111 response data for a current, noncanceled session.
- Always delegate every instrumented response (including canceled and unmatched ones) to the original stock response callback.
- If a request errors or its response is lost, retain its tombstone and eventually reject new instrumentation when all eight slots are occupied. This sacrifices availability for ambiguity avoidance.

## Offline checks

- Host `cc -std=gnu11 -Wall -Wextra -Werror -fsyntax-only` succeeds with combined mode 0 and 1.
- `python3 tests/run_step115_host.py` extracts the **actual helper implementation** from `altscreen.c`, compiles with ASan/UBSan, UBSan, and unsanitized modes, and exercises canceled records, alias rejection, generation switching, token-based cancellation, synchronous completion, full capacity, and ticket overflow.
- **NOT** tested against the target ARM/uClibc toolchain following these changes; not runtime verified.

## Unresolved risks — no flashing

1. The `cf_release(replaced_streams)` operation introduced by Step 112 requires proof of stock CoreFoundation array ownership at the actual callsite (e.g. disassembly of matched stock firmware).
2. A session may teardown **after** stream 111 has been inserted into the outgoing native request array but **before** the stock HTTP call; the existing hook has no validated way to remove stream 111 from the already serialized message. The new callback logic cannot prevent this transmission.
3. A stock HTTP send that fails without ever invoking a callback retains a tombstone. After eight such requests, stream-111 instrumentation is disabled until restart. This is an intentional fail-closed tradeoff, not a recovery mechanism.
4. Callback message pointer identity still relies on stock message lifetime guarantees. The code does not retain or own stock message objects. A callback after actual memory reuse/UAF in stock code cannot be made safe by this shim.
5. Stock callback address (`0x2ec7c`), message structure offsets (`0x904`, `0x49c`, `0x4a0`) and CoreFoundation function prototypes are reverse engineered and not runtime verified on the target.

**Keep the stock recovery archive and do not emit or install a flashable package.**
