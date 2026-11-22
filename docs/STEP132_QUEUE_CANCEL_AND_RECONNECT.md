# Step 132 — Queued HTTP cancellation, queue destruction and reconnect safety

**Status:** verified-stock static evidence + source-derived host regression + new read-only collection script. **No timeout-based reclamation, firmware packaging, flashing or device-runtime validation.**

## Scope

Step 131 resolved the narrow case of nonzero `HTTPClientSendMessage` returns: on the verified stock AK3918 ELF, those are pre-enqueue failures and their shim request slots can be reclaimed. **Step 132 addresses the fundamentally different case of a successful enqueue (`rc == 0`) followed by cancellation, disconnect or a missing callback.**

The source material is the stock `sdDongle` ARM disassembly (SHA-256 `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`) recorded in earlier read-only extracts, and [Step 128's ownership audit](STEP128_DISASSEMBLY_AND_ADMISSION_GATE.md). It is not the OMKE MIPS executable.

## Established native lifecycle

1. Stock `HTTPClientSendMessage` at `0xa6974` retains the message and client and enqueues `0xa6040(msg)` on the client queue through `0xa1900`. It returns **0 for accepted/enqueued** requests; a zero return does **not** establish completion.
2. Dispatch queue drain `0xa304c..0xa30b0` extracts a node, unlocks the queue mutex and invokes the callback; `0xa6040` appends the HTTP message into the client's message list and releases the client retain.
3. Normal message completion `0xa4c18..0xa4c58` invokes `msg+0x904` and then releases the message. The shim callback delegates to the stock callback, including for canceled/stale requests.
4. On the ordinary client invalidation path, `0xa6584` enqueues `0xa4f30`, which invokes the client error handler `0xa4d7c`. That handler drains the client's **message list** via message completion, including its callbacks.
5. The *separate dispatch queue destructor* at `0xa01b8` explicitly inspects `queue+0x30` for **pending work nodes** (conditional branch at `0xa0250..0xa0294`). The previously captured excerpt logs the nonempty state and moves on to mutex/global cleanup. This is **not proof that pending queue work callbacks execute on destruction**. Nor does draining the HTTP client's message list cover a send node which has not yet been handed from the dispatch queue into that list.

## Crucial unproven guarantee

We cannot yet establish that *all accepted HTTP sends* eventually reach `msg+0x904` across abrupt queue destruction, process termination, concurrent client invalidation, or an abnormal disconnected state. A canceled request record stores only the original message **identity** and is not an owned CF reference; forcibly freeing the record on a clock timeout or new session could allow a late callback to be associated with an allocator-reused address.

**No code now reclaims an accepted request because of elapsed time or teardown.** Record retention is intentional fail-closed behavior, not a memory leak in the native object; the shim metadata table is bounded to eight entries.

## Step 132 source-derived host stress

`tests/run_step132_callback_reconnect.py` compiles the actual `combo_request` helpers from `altscreen.c` and tests:

- Eight accepted requests occupy all slots; a ninth request and a duplicate message identity are rejected.
- Invalidating a session marks those records canceled but **does not free them**; a new session is not allowed to reuse them until the old callback is seen.
- Late callbacks in reverse order free the corresponding slots and cannot start a stale-generation connection.
- **128 repeated reconnect cycles** with timely late callbacks can reclaim/reuse slots without permanent saturation.
- Missing callbacks across many new-session attempts deliberately keep the table full; no speculative timeout-based cleanup or pointer alias is allowed.
- Normal accepted responses still propagate a matching valid-generation connection identity; the shim's source still calls the original stock response callback.

Tests are host simulations of the current source helper functions, **not** a simulation of the native dispatch queue, HTTP error handler, Apple CarPlay or the user's physical dongle.

## Step 132 read-only extraction

`scripts/step132_extract_queue_cancellation.sh` checks the **exact stock binary SHA-256** and uses read-only Docker mounts to extract:

| Address range | Reason |
| --- | --- |
| `0xa01b8..0xa0384` | Dispatch queue destructor / pending node handling |
| `0xa304c..0xa30bc` | Serial queue pop, unlock and callback |
| `0xa058c..0xa06e8` | Concurrent queue drain comparison |
| `0xa4c18..0xa4c64` | HTTP message completion, callback and release |
| `0xa4d7c..0xa4f2c` | Client error handling and message-list drain |
| `0xa4f30..0xa4f60` | Client invalidation callback |
| `0xa6584..0xa65bc` | Invalidation enqueue |
| `0xa6040..0xa6078` | Send dispatch callback |
| `0x2a74c..0x2a7a8` | Car-side global client invalidation |

To create the next report on the Mac:

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step132_extract_queue_cancellation.sh
```

Output: `~/Desktop/AK3918_step132_queue_cancellation.txt`. The script refuses a wrong stock SHA-256 and does not build, alter or package firmware. Attach this report for targeted analysis of queue destruction/callback delivery semantics.

## Local extraction validation — user-reported

After fast-forwarding the experimental branch from `263596b` to `02b7a0e`, the user ran `bash scripts/step132_extract_queue_cancellation.sh` on their Mac. The command reported:

```
PASS: Step 132 verified-stock queue and cancellation report at /Users/wademacintosh/Desktop/AK3918_step132_queue_cancellation.txt
No firmware was modified, packaged, installed or flashed.
```

The script checks the original stock ELF SHA-256 and ensures all required ARM routine-entry addresses were captured. **This confirms successful extraction only**: the complete report has not yet been supplied for review, so it does **not** establish whether abandoned pending queue nodes receive `msg+0x904` or can be discarded without callback delivery.

The source-derived reconnect and read-only script checks passed [GitHub Actions run 44978247878](https://github.com/wmacintosh/ak3918-Wireless-Carplay-Audi-Virtual-Cockpit/actions/runs/44978247878) at commit `02b7a0e`. The report itself remains the next evidence input.

## Deployment decision

The Step 129/130/131 source/ELF checks are distinct from live firmware validation. The combined stream-111 feature remains experimental, disabled by default; the optional test archive is not authorized for installation as a consequence of these findings. No change to `main`, stock recovery archive, or historical firmware is required.

**Next evidence gate:** establish whether the dispatch queue's pending work can be destroyed without running `0xa6040`, and how client invalidation is sequenced relative to that queue drain. Do not implement global ticket resets, timeouts or manual CF releases without a proven guarantee.
