# Step 146 — Physical exterior and retail packaging identification

**Status: packaging/product family identified from two user-provided photographs; exact PCB/bootloader revision remains UNKNOWN. No target hardware was opened or probed and no firmware was built, patched, packaged or flashed.**

## Directly observed in the owner's photographs

The owner supplied two color photographs of the unmodified exterior and retail packaging in the current conversation. These photographs were examined in context. **Photograph bytes were not uploaded to the public project repository**, and the barcode's unique identifier is intentionally omitted.

| Attribute | Evidence and confidence |
| --- | --- |
| Retail packaging model | **`RM-KPL083-2`**, clearly printed above the barcode — **direct photograph** |
| Printed manufacturer | **Huizhou Ruirong Huake Electronics Co., Ltd.**, listed on the product label — **direct photograph** |
| Product description | 2-in-1 wireless CarPlay / Android Auto adapter, described as a Smart Box — **direct photograph** |
| Exterior dongle | Tiny black rounded-square face, silver/gray outline, central white round/wedge logo and a transparent/green protective-film pull tab — **direct photograph** |
| PCB identification, revision silkscreen | **Not visible**; the photographs show the closed enclosure and retail box, not an actual board |
| Live device software identity | `AK3918AN / suding`, `system_version=20260411104900CA`, `protocol_version=20261008165915` — **separate Step 144 physical CGI report** |

Do **not** interpret a packaging SKU or retail barcode as an internal SoC, loader revision, flash chip, or hardware recovery interface. The printed manufacturer is a useful contact for requesting factory-specific technical recovery instructions but **does not** itself establish the board maker/revision.

## Web corroboration (retail family only, not board identity)

Searches for the *exact* `RM-KPL083-2` with recovery/board terms did not return validated PCB, UART pads or out-of-band restore documentation. Broader **`RM-KPL083`** references are available:

- [EzoneTronics RM-KPL083 manual](https://manuals.plus/ae/3256811996136302) describes a similarly named 2-in-1 wireless CarPlay / Android Auto product and general SmartBox/OTA workflows, but specifies a **Cortex-A7** CPU and AIC8800 wireless chipset.
- [ANYFAR RM-KPL083 / RM-KPL078 manual](https://manuals.plus/ae/1005012683258387) is evidence that the `RM-KPL083` name is marketed under more than one brand.
- [Example Huizhou Ruirong Huake Electronics RM-KPL083C product review](https://minkara.carview.co.jp/userid/2994900/car/3893158/14083187/parts.aspx) concerns a **different suffix `P4-RM-KPL083C`**, not the owner's exact `RM-KPL083-2`.
- [Anyka's AK3918AV100 SoC product page](https://anyka.com/en/article/17/9.html) describes an **ARM926EJ-S**, fundamentally different from Cortex-A7; this is architectural background, not proof of this exact PCB.

**Critical mismatch:** This project statically verified an ARM32/uClibc executable and develops for the AK3918 ARM926EJ-S family, whereas the generic `RM-KPL083` retail manual names Cortex-A7. This is a reason to **reject** assuming that the generic retail manual's chipset/firmware/boot/recovery steps are necessarily compatible. It is not evidence the user's `AK3918AN` endpoint was misidentified. Multiple internal revisions can share broad retail naming; the cause of the mismatch has not been established.

No public result from these sources establishes an RM-KPL083-2 **PCB revision**, verified external rescue-mode handshake, correct SPI flash offsets, bootloader command sequence or manufacturer-supplied full-device recovery image.

## Safe, targeted next evidence

1. **Unpowered exterior inspection only:** photograph the *back* and *USB connector end* of the actual adapter (the photos so far show the front and retail package); capture any molded text, tiny revision number or labeling. Do not open the adapter solely on a guess that UART pads exist.
2. **Manufacturer-specific support request:** Ask Huizhou Ruirong Huake Electronics Co., Ltd. for the RM-KPL083-2 hardware/PCB revision, the exact AK3918AN / Suding system/protocol combination, any approved offline recovery method if Wi-Fi/CGI no longer boots, and whether they can provide the matching official rootfs/system-library identities (or a documented method to obtain them without writing firmware). Avoid sending a full serial/barcode identifier to public forums.
3. **No stock/experimental flash yet.** The verified original tar contains only application files and its software restore depends on booted Wi-Fi/CGI. The exact installed `libc.so.0` / `ld-uClibc.so.0` and a board-specific non-CGI restore path are **not proven**.

## Release gate

Step 146 narrows the **retail/packaging provenance** but does not clear the target-loader, callback/runtime or independent-recovery gates. Continue to keep the combined stream-111 test archive separate from the legacy `ak_hook.tar`; no new flashing permissions are implied.

**Repository changes in Step 146 are documentation only.** No user-uploaded photographs or identifying barcode values were committed, and no device settings or firmware files changed.
