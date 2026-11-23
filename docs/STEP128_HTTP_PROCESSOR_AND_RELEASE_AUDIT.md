# Step 128 — HTTP processor and retained-message release audit

**Status: read-only ARM evidence from Step 127, with an unverified message-release and session-lifetime boundary. No flashing, packaging or binary edits.**

## Input and origin

Source: user-uploaded `AK3918_step127_queue_completion.txt`, extracted using the verified original AK3918 stock `sdDongle` ELF (SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`). The OMKE AX1800M repository remains our high-level protocol reference; AK3918/ARM callsites are established only from the user's own stock binary.

## Newly established handoff

The stock HTTP send routine at `0xa6974`:

1. Retains HTTP message with `0x82c74` at `0xa6a4c`.
2. Retains HTTP client with `0x82c74` at `0xa6a54`.
3. Saves client in `message+0x8ec` at `0xa6a5c`.
4. Enqueues `(message, callback=0xa6040)` via `0xa1900` at `0xa6a6c`.

`0xa6040` is an **enqueue-dispatched callback**, not demonstrated to be the final response callback.

The Step 127 disassembly of `0xa6040..0xa6070` shows:

| ARM address | Native operation | Interpretation |
| --- | --- | --- |
| `0xa6044` | `ldr r4, [r0,#0x8ec]` | Read client from the dispatched message |
| `0xa604c` | `str r3, [r0,#8]` where r3=0 | Initialize message intrusive next pointer |
| `0xa6050` | `ldr r3, [r4,#0x4a0]` | Load client message-list insertion pointer |
| `0xa6054` | `str r0,[r3]` | Append message to client pending list |
| `0xa6058..0xa605c` | `r0=message+8`, save at `client+0x4a0` | Advance client list tail insertion pointer |
| `0xa6060..0xa6064` | `bl 0xa53fc(client)` | Kick native HTTP client processor |
| `0xa6068..0xa6070` | `r0=client`, tail branch `0x82c78` | **Release client retain acquired at send/enqueue** |

**Confirmed:** client retain/release is balanced along the ordinary executed dispatch callback path. The queue may have cancellation/error paths which bypass this callback and must be checked separately.

**Not yet confirmed:** where the message's separately acquired retain is released; whether `0xa53fc` invokes the registered HTTP response callback synchronously or asynchronously; whether the receiver session remains alive while callbacks are pending.

## Other Step 127 observations

- The candidate range `0xa14a0..0xa18d8` mostly contains wait/timer and condition-variable logic plus a global notifier; it is **not** evidence that the HTTP message queue has been fully drained or that the retained message is released.
- `0xa1798..0xa17c0` cleans up an event source and releases a separate global object, but nothing in this excerpt identifies it as the outgoing HTTP message.
- The `0xa63d0..0xa6974` range includes HTTP client construction and socket callbacks, but does not show a balanced `0x82c78` call for the outgoing message retained by `0xa6a4c`.
- Step 125 source-level test still reproduces admission before teardown, followed by native HTTP send after teardown. The retained client may mitigate premature client free; this alone does not protect the receiver session.

## Step 128 read-only collection

From the existing local repository:

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step128_extract_http_processor.sh
```

The script generates `~/Desktop/AK3918_step128_http_processor.txt` with disassembly around the complete `0xa53fc` client processor and adjacent message cleanup / stock response routines. It verifies the exact stock SHA-256, uses read-only container mounts and preserves previously successful reports on failure. Source-only CI checks validate syntax and expected address ranges; they do not validate native runtime behavior.

## Deployability

Do not change native ownership or hold `g_state_lock` across stock HTTP code based solely on this trace. Do not package or flash an `AK_ENABLE_COMBINED_CLUSTER=1` firmware image: the Step 125 teardown-to-send race remains unclosed and its actual impact is unresolved.

**Next decision after reviewing Step 128:** identify normal and canceled/error-path releases for the message retain, and verify whether `0xa53fc` can synchronously invoke `shim_screen_response` or reenter finalization. Only then consider a correctly ordered send barrier or lifetime pin.
