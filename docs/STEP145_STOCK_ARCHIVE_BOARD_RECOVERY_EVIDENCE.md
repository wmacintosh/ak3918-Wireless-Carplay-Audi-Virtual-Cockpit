# Step 145 — What the verified stock archive can tell us about the board and recovery

**Status: completed offline on GitHub CI.** Six synthetic/real-archive negative-control tests passed and the actual SHA-pinned original archive was inventoried **without network, target hardware, extraction to disk, firmware build, archive modification or flash**.

## Primary evidence

The current [Step 145 CI inventory transcript](../evidence/AK3918_step145_stock_recovery_inventory_ci.txt) covers the original `stock_ak_202610081659.tar` at SHA-256 `a4ee31452833cc38cf4a3839adaa75b9b34fd0a9d2ed006e0c9b34ae7539dba3`. The archive is exactly **five regular files**, not a full device image: `sdDongle`, `libSdAuto.so`, `libSdCommon.so`, `libSdSampleRate.so`, `libSdUtils.so`. The original `sdDongle` hash remains `b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1`.

The read-only scanner at `scripts/step145_stock_recovery_inventory.py` counts a narrowly allowlisted set of literal byte sequences only; it does not dump arbitrary firmware strings, host identifiers, MAC addresses, secrets or serial numbers. The observed nonzero counts are:

| Original archive member | Exact allowlisted marker occurrences |
| --- | --- |
| `sdDongle` | `suding` (37); `yunlian` (1); `/lib/ld-uClibc.so.0` (1) |
| `libSdCommon.so` | `suding` (14); `/proc/mtd` (1); `/dev/mtd` (1) |
| `libSdAuto.so` | `suding` (1) |
| `libSdUtils.so` | `recovery` or `Recovery` (1) |
| `libSdSampleRate.so` | No hits from the fixed allowlist |

**These are embedded string references, not physical hardware observations.** In particular, `yunlian` in a vendor application does **not** prove the user's board is a Yunlian hardware revision; a `/proc/mtd` literal in a library does **not** give the device's actual partition table; a `recovery` string is **not** a proven independent recovery procedure.

Because no `u-boot.bin`, `uImage`, rootfs, DTB, full flash image, `libc.so.0`, or `ld-uClibc.so.0` file is in the package, neither the whole-device recovery route nor the currently installed loader can be proven from this tar. The historical `--stock` recovery requires the dongle to boot and serve HTTP/CGI and therefore does **not** protect against a nonbooting unit.

## Live-device evidence (Step 144)

The [live dongle GET](../evidence/AK3918_step144_device_identity_user_terminal.txt) returned:

- `platform=AK3918AN`
- `custom=suding`
- `system_version=20260411104900CA`
- `protocol_version=20261008165915`

Do not mistake the protocol-version string for the system-version string. An identity match does **not** verify that `sdDongle`, libc or bootloader files in physical flash are identical to anything in the development toolchain or stock archive.

## External research — similar hardware, NOT identified as this PCB

Two independent GitHub reports [catplay-firmware issue 2](https://github.com/catplay-labs/catplay-firmware/issues/2) and [catplay issue 32](https://github.com/catplay-labs/catplay/issues/32) describe other adapters reporting `platform:AK3918AN` and `custom:suding` with **different** version strings or alias fields, including `v851se-yunlian-cp`. They demonstrate a real pitfall: identical platform/vendor strings or branding can cover differing product variants. In the other reports, a recovery trigger designed for Ingenic devices did not enter USB recovery on the AK3918 family; this is **not** proof of the user's board's behavior, pinout, bootloader implementation, flash map or ability to recover. These reports should not be treated as flashing instructions or permission to try generic exploitation/recovery commands.

A different AK3918AV130 *camera* project and SoC datasheet may be useful architecture background, but neither can establish the physical pads or SPI-NOR flash layout for the user's Suding CarPlay dongle. Generic AK3918 instructions may permanently damage the wrong PCB.

## Remaining requirements and practical next evidence

| Required fact | Current evidence | Safe next source |
| --- | --- | --- |
| Actual PCB maker/revision and external model | `AK3918AN/suding` reported by CGI only | Clear unaltered exterior photos of both sides, model label and packaging sticker; do not infer physical revision from a product listing |
| Installed `libc.so.0` and `ld-uClibc.so.0` identities | Only Buildroot *toolchain* `libc.so.0` SHA-256 known from Step 143 | Genuine manufacturer firmware rootfs or authorized existing read-only shell; verify hashes and export/version tables separately |
| Actual `/proc/mtd` mapping or flash chip | One embedded `/proc/mtd` reference in `libSdCommon.so`, **no partition map** | A previously obtained unmodified device boot log, legitimate vendor hardware documentation or carefully identified physical flash markings (only if already safely accessible) |
| Recovery when Wi-Fi/CGI is unavailable | **Not demonstrated** | Device-revision-specific vendor recovery documentation, independently proven offline bootloader console or hardware-programmer procedure with known-good full-flash backup |

For physical photos, keep the dongle **disconnected from power**. Exterior identification is preferred. Do not short unknown pads, attach a voltage source, probe an unknown serial header, invoke the CGI updater or attempt software exploits merely to obtain libc. The current project has neither a validated full-system backup nor a proven out-of-band unbrick technique.

## Safety gate and next step

**Step 145 result:** stock archive scope and embedded markers **verified**; actual board revision, installed rootfs/libc, and independent recovery **remain unknown**. Experimental stream-111 package/install/flash remains on hold, while all Step 141–144 tests retain their existing passing status.

**Next useful task:** match photos of the actual unpowered dongle's exterior/model markings to **board-specific evidence**; if physical identity cannot be resolved non-invasively, treat non-CGI recovery as unverified rather than inventing a UART pinout or use another board's SPI map. No additional firmware compilation is needed to do this.
