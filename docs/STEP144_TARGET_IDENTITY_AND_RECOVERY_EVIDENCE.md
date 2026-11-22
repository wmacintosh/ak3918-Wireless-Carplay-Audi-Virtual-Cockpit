# Step 144 — Device-specific read-only fingerprint and recovery evidence boundary

**Status: actual Mac/device identity probe PASSED** (user-pasted terminal output). The target library files, UART console and out-of-band hardware recovery method remain unknown. **Do not package or flash the combined stream-111 experiment.**

## Actual Step 144 result — observed on the physical dongle

The user connected to their dongle's SmartBox Wi-Fi and ran `scripts/step144_target_identity_readonly.py --probe-version` at WIP commit `f72a8b8f3576`. The reported probe called the single allowlisted GET endpoint and returned `PASS: STEP144 READ-ONLY HTTP DEVICE IDENTITY`. The user-pasted [relevant terminal lines are archived](../evidence/AK3918_step144_device_identity_user_terminal.txt).

| Returned field | Value |
| --- | --- |
| `platform` | `AK3918AN` |
| `custom` | `suding` |
| `system_version` | `20260411104900CA` |
| `protocol_version` | `20261008165915` |

**Important:** The earlier README calls `20261008165915` a CarPlay firmware version. The actual device reports that string as **`protocol_version`**, whereas **`system_version` differs**. These are not interchangeable and the response alone does **not** establish binary equality with the original `stock_ak_202610081659.tar` archive, nor proof that the installed root filesystem matches the Buildroot libc used for development. The difference is not by itself evidence of corruption or incompatibility; the field semantics require separate device-specific evidence.

This probe validates device platform/vendor identity and confirms its ordinary version CGI can respond. It provides **no physical recovery guarantee** if CGI becomes unavailable, and cannot read or hash installed `/lib/libc.so.0` or `/lib/ld-uClibc.so.0`. These remain hard open gates for flashing combined stream 111.

## Established before this step

The [Step 143 Mac audit](../evidence/AK3918_step143_loader_recovery_audit.txt) found all **33 of 33** strong `libSdH.so` imports in the **development** uClibc `libc.so.0` (SHA-256 `42891edc20c0f47833248f0dc312199e051e966e2a9b0e859f0137ebe55603d7`). This is a valid available-provider result, not proof that the dongle runs the identical libc or that `ld-uClibc.so.0` can relocate the actual experimental library. Its reported `DT_NEEDED=libc.so.0` and BIND_NOW contract are still untested on target.

The checked [historical `flash_ak.py`](../flash_ak.py) exposes exactly one clearly documented benign identity read: `GET http://192.168.200.1/cgi-bin/getversion.cgi`. Even its `--check-only` path uploads firmware chunks, so **never invoke the installer for a read-only device probe**. Other firmware CGI paths (including `submition.cgi`, `downfile.cgi` and `reboot.cgi`) are excluded.

## Step 144 collector

`scripts/step144_target_identity_readonly.py` has two modes:

- **No arguments:** prints the scope and makes **no network requests**.
- **Explicit `--probe-version`:** issues **one HTTP GET** to the exact historical `192.168.200.1/cgi-bin/getversion.cgi` endpoint, using a four-second timeout, no redirects and a 4 KiB response limit. Requires **both** `platform:AK3918AN` and `custom:suding` and fails closed on missing/incorrect identity.

Only allowlisted firmware/model fields are printed; serial numbers, MAC addresses, activation data and pairing material are never echoed. The script runs no shell, uploads, commands, filesystem requests, broader port scans or firmware updates. It cannot report the actual target `libc.so.0` or physical board revision.

**To run on your Mac:**

1. While connected to the Internet, update the existing isolated research branch:

   ```bash
   cd "$HOME/AK3918_GitHub"
   git pull --ff-only
   ```

2. With the dongle powered, join its **SmartBox_XXXX** Wi-Fi (the local network may have no Internet).
3. From Terminal:

   ```bash
   set -o pipefail
   python3 scripts/step144_target_identity_readonly.py --probe-version \
     | tee "$HOME/Desktop/AK3918_step144_device_identity.txt"
   ```

A `PASS: STEP144 READ-ONLY HTTP DEVICE IDENTITY` proves only that the expected device answered the exact GET with model/vendor metadata. It does **not** prove firmware binary identity, the installed root filesystem library versions, flash layout, bootloader console or independent recovery. A failed connection is **not** evidence of a bad ELF; check that the Mac is connected to the dongle's network rather than running an updater.

The test `tests/test_step144_target_identity_readonly.py` uses strictly **fake** HTTP responses; CI never requests an actual device.

## Recovery-specific evidence: what we have and what we do not

| Evidence | State | Practical meaning |
| --- | --- | --- |
| Original vendor application and four associated libraries | **Verified** SHA-pinned | Sufficient for the original ARM patch/ELF structural check, not a full system backup |
| Full installed root filesystem, `/lib/libc.so.0` or `/lib/ld-uClibc.so.0` | **Not obtained** | Cannot prove physical loader's symbol and version compatibility |
| `/proc/mtd`, board printing, flash-chip identity, U-Boot configuration | **Not obtained** | No board-specific MTD layout or safe restore command |
| Verified UART TX/RX/GND pads and working bootloader console | **Not obtained** | No demonstrated offline recovery if Wi-Fi/CGI is unavailable |
| Historical `--stock` over normal Wi-Fi/CGI | **Available only if boot/HTTP works** | A software recovery path, **not** an unbrick guarantee |

External research describes *another* Anyka AK3918-based CarPlay dongle for which a recovery trick intended for the **Ingenic** family did not work ([catplay-firmware issue #2](https://github.com/catplay-labs/catplay-firmware/issues/2), opened August 15, 2026). This is **not proof of the board layout, firmware or recovery capabilities of this specific Suding dongle**. Do not use somebody else's recovery trigger, SPI flash map, U-Boot command, UART pinout, or image file on this board based on shared CPU branding alone.

For the next independent-recovery investigation, preserve non-invasive evidence: the exact dongle's exterior product/model markings and any *already available* board-revision documentation or photographs, plus evidence of a **legitimate read-only way** to inspect the target root filesystem. Do not open a powered enclosure, probe unknown pads, exploit the CGI update interface for code execution, or write to flash. If the owner later has an authorized existing shell or a complete trusted firmware/rootfs image, separately verify `libc.so.0`, `ld-uClibc.so.0`, their cryptographic hashes, GNU symbol-version requirements, ARM EABI and available exports.

## Gate after Step 144

The actual Step 144 run confirmed AK3918AN/Suding **identity** over a benign GET, but **must not claim real runtime loader compatibility** without exact installed library files or a read-only shell/image, and **must not claim unbrick support** without verified board-specific bootloader or recovery evidence. The WIP stream-111 build remains unapproved for deployment.

**No change to `altscreen.c`, `build_hook.py`, `flash_ak.py`, original firmware, stock recovery or `main`.**
