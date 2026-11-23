# Step 123 — Native HTTP message correlation (source-only WIP)

**Status: not verified on device; do not flash.** Evidence comes from the original AK3918 stock `sdDongle` ARM disassembly (SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`), captured in Step 121.

## Evidence

- `0x2f6d0`: initializes native HTTP message slot `[sp,#0x2c]` to zero.
- `0x2f784`: passes `&[sp,#0x2c]` to native message creation `0xa6d08`; creation writes the allocated object to this pointer.
- `0x2fad8`: passes `&[sp,#0x34]` to the array ensure hook `0x2fadc`. The message object is at the neighboring `[sp,#0x2c]` slot, so `*(void **)((uintptr_t)streams - 8u)` is the existing message identity at this specific verified callsite.
- `0x2fb88`: loads message from `[sp,#0x2c]` to `r1` before HTTP submission `0x2fbb0`.
- Early exits: `0x2fb04` takes `0x2fb08..0x2fb38` toward shared cleanup on serialization failure; `0x2fb58` takes `0x2fb5c..0x2fb80` toward shared cleanup on message-setup failure. Neither reaches the send hook.
- Cleanup releases `[sp,#0x34]` at `0x2fe1c..0x2fe28` and `[sp,#0x2c]` at `0x2fe2c..0x2fe38`.

## Change

- Store the native message pointer in `combo_build.message` at array publication. It is an **identity** only: the shim does not retain it or dereference it after the array-ensure hook.
- Require the send-hook message pointer to match the active build record, in addition to the thread/generation checks, before claiming a response callback. A different stock-only message is left untouched.
- Upon entering a subsequent array-ensure hook on the same thread, cancel older builds without deleting their records. This prevents an old orphan from falsely matching an allocator-reused message pointer. If an older injected request subsequently arrives at send, it is rejected.
- Update Step 120 host tests to cover different-message isolation, canceled stale builds and pointer reuse.
- Update Step 122 static CFG analyzer to identify independent bypassing branch decisions rather than only distinct terminal returns. Both early exits converge on the same final return.

## Validation and remaining risks

GitHub Actions host C syntax checks, Step 115 and Step 120 helper tests, shell tests, and Step 122 analyzer tests pass following these changes. This does **not** establish ARM/uClibc binary ABI correctness, a tested firmware build, or in-car functionality.

**Unresolved deployment blockers:** finalizer may invalidate the session after pre-send validation but before/during native HTTP submission; native send/teardown lock ordering and callback reentrancy are unknown; `pthread_self()` and stock message allocator behavior have not been dynamically traced; late callback ownership and stale pointer reuse need further confirmation. A no-flash source-only branch cannot close these risks through host tests alone.

The default `AK_ENABLE_COMBINED_CLUSTER=0` remains unchanged. Do not package or install the experimental combined firmware. Preserve the original stock recovery archive.
