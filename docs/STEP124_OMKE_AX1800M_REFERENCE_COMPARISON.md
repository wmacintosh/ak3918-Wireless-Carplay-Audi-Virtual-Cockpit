# Step 124 — OMKE AX1800M reference compared with AK3918AN (read-only research)

Status: source-only research, 2026-11-21. **Do not flash an AX1800M image to an AK3918AN dongle.** No firmware was packaged, modified, or tested on the device by this review.

## External reference

Source: [OMKE/wireless-carplay-virtual-cockpit](https://github.com/OMKE/wireless-carplay-virtual-cockpit), public `main` branch. Its README reports an in-car wireless Virtual Cockpit success on 2026-10-19 in a 2017 Audi A5, MHI2Q with MIBSI P5092. Evidence is author-reported and hardware-specific.

Relevant reference material:

- [README](https://github.com/OMKE/wireless-carplay-virtual-cockpit/blob/main/README.md) and [How it works](https://github.com/OMKE/wireless-carplay-virtual-cockpit/blob/main/docs/HOW_IT_WORKS.md)
- [Source of experimental shim](https://github.com/OMKE/wireless-carplay-virtual-cockpit/blob/main/src/altscreen.c)
- [Research status](https://github.com/OMKE/wireless-carplay-virtual-cockpit/blob/main/research/docs/STATUS.md)
- [Client stream map](https://github.com/OMKE/wireless-carplay-virtual-cockpit/blob/main/research/analysis/p4-client-screen-map.md)
- [Audi display descriptor](https://github.com/OMKE/wireless-carplay-virtual-cockpit/blob/main/research/analysis/carinfo/audi_displays.json)

## What transfers conceptually

1. **Architecture of the proxy:** iPhone-to-dongle receiver must expose altScreen 111 and accept/decrypt its incoming video, while dongle-to-car client must SETUP another stream 111 and encrypt/send frames. Maintaining the existing stream 110 is essential.
2. **Phone receive cipher:** per-frame ChaCha20-Poly1305 when a pair-verify session is active, with the 128-byte frame header as AAD, little-endian 64-bit frame nonce and 16-byte tag. Stock AES-CTR is an alternative when the pair-verify path is absent. This must be validated against AK3918's stock key-derivation ABI and frame captures.
3. **Car send protocol:** independent AES-CTR stream/connection context for the cluster, 128-byte video/config headers, config-before-IDR ordering and a dedicated socket; stock main-screen push routines may hard-code display dimensions.
4. **Activation:** a `showUI` command with `maps:/car/instrumentcluster/map` should happen from a safe worker context rather than synchronously inside SETUP if native implementation can dispatch synchronously.
5. **Known hazards:** global streamConnectionID, singleton video callbacks/config, stale HTTP callback/context lifetimes, teardown during send, and missing callback completion must be audited separately on the ARM firmware.

## What must NOT be copied

| Dimension | OMKE working reference | This AK3918 project |
| --- | --- | --- |
| Dongle SoC/toolchain | AX1800M, MIPS32r2 little-endian; Zig MIPS build | AK3918AN, ARM; ARM/uClibc cross toolchain |
| Firmware source | `ax_202609051445` | `ak_202610081659` |
| Addresses/hook ABI | MIPS GOT and `jalr t9`; e.g. `0x46c2fc` | ARM BL hooks and AAPCS; stream ensure `0x2fadc`, send `0x2fbb0` |
| Cluster dimensions | OMKE MIBSI: 1440×540, type 111 | AK source currently sets 1440×542; requires exact target MMI `/info` verification |
| Head unit | OMKE documented MHI2Q P5092 with MIBSI installer restricted to that version | User's previously identified MHI2Q_US_AUG22_P5087; do not apply OMKE's P5092 installer |
| Runtime status | OMKE reports working wireless VC map in one car/dongle | AK combined-mode remains unvalidated; previous tests are host/static only |

The common UUID `b7e6c5a0-2222-4000-8000-000000000002` and cluster-map URL are useful protocol references but not proof that the AK target's car-side display descriptor, dimensions or initialURL are identical.

## Does OMKE solve the Step 120/123 send race?

**No, not directly.** OMKE's code is for a different ISA and firmware. It explicitly lists an outstanding HTTP message/body leak and limited reconnect testing; its success on AX does not prove thread ownership or transport teardown ordering on AK.

Our verified AK `sdDongle` Step 121 disassembly shows two native exits between array insertion and send: `0x2fb04` serialization failure, and `0x2fb58` message setup failure. They join common cleanup. The Step 123 source-only message-identity change uses the AK-specific `[sp+0x2c]` message pointer to reject mismatched requests; it still cannot close the send/teardown TOCTOU window. These are distinct from OMKE's successful data path.

## Recommended next audit (no flashing)

1. Compare the AK implementation with OMKE's **data-flow state machine**, not its physical addresses or binary packaging.
2. Obtain the actual target Audi `/info` alt display entry to settle 1440×540 versus 1440×542 and confirm the UUID and viewArea/safeArea.
3. Validate AK ChaCha20-Poly1305 / AES-CTR key derivation, IDR/config send order and response callback with controlled host tests and verified stock disassembly.
4. For combined-mode, separately prove HTTP send/finalizer ordering and error cleanup before any runtime test; prefer stock-safe behavior while uncertainty remains.
5. Preserve known-good stock recovery firmware. **Do not install OMKE's AX1800M archive or P5092 MIBSI package on AK3918/P5087.**

This document is a cross-platform research comparison, not a claim that the existing AK firmware works wirelessly in the Virtual Cockpit.
