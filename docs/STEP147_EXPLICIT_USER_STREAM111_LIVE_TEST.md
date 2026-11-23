# Step 147 — User-requested live experiment: build, probe and install stream 111

**Purpose:** The owner explicitly wants to test the combined CarPlay/Virtual Cockpit experimental firmware on their AK3918AN/Suding dongle. This document supplies actionable, gated tooling while retaining the *unresolved risk* of bricking. The experimental firmware has never successfully run on this physical device. **This is a test procedure, NOT a validated release.**

## Inputs already verified

| Gate | Observed |
| --- | --- |
| Step 141 | Original `sdDongle`, five stock library members, hook locations and archive hashes passed |
| Step 142 | Docker-built patched ELF and `libSdH.so` passed full static ELF audit |
| Step 143 | 33/33 strong hook imports matched **development** libc exports; installed target libc not verified |
| Step 144 | Actual device `platform=AK3918AN`, `custom=suding`, `system_version=20260411104900CA`, `protocol_version=20261008165915` |
| Step 145–146 | Original recovery tar is application-only; packaging reads RM-KPL083-2; no validated independent hardware recovery |

The version endpoint reports `20261008165915` as a **protocol** version, not a system version; Step 147 matches **both** fields exactly. A matching GET still does not prove exact physical libc/loader bytes.

### Known limitations and deliberate risk

- The combined stream-111 source has passed host tests; its session lifecycle, asynchronous callbacks, video handshake and virtual cockpit transport have not been verified on the dongle.
- `libSdH.so` has `DT_NEEDED=libc.so.0`, `BIND_NOW` and 33 strong imports. All names were found in Buildroot's libc, but the dongle's **installed** libc/loader was not retrieved and may differ.
- A bad boot or loader failure could make the dongle stop advertising Wi-Fi or serving HTTP. In that state, `flash_ak.py --stock` is **not** a usable recovery procedure. We do not have a full-flash backup, board-revision-specific UART/bootloader image or independently verified unbrick method.
- The owner has declined contacting the manufacturer or opening the enclosure, so these gaps cannot be cleared by the methods proposed earlier. **Only proceed with `--install` if accepting possible permanent loss of the adapter.**
- The tested firmware is for the dongle's application, not a patch to the car's MMI or Audi VC firmware.

## 1. Prepare exact experimental package while online

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
bash scripts/step147_prepare_test_archive.sh
```

This command uses the already installed `ak3918-buildroot:latest` image, the read-only `ak3918-buildroot-work` toolchain volume and original inputs. It reruns Step 141, then in a no-network Docker workspace builds the **test-only** combined+phone-commands tar using `build_hook.main()`, reruns the exact Step 142 ELF auditor, confirms the known-good static build hashes, checks all six tar members and emits only these two host files:

```text
~/Desktop/AK3918_Stream111_Test/ak_hook_step128_test.tar
~/Desktop/AK3918_Stream111_Test/step147-manifest.json
```

The build **does not install or upload** firmware and leaves the historical `ak_hook.tar`, stock recovery tar, `main` and original source files untouched. It refuses to overwrite an existing output directory. The distinct test archive is **not** silently renamed or substituted into the old `flash_ak.py`.

**Required static hashes inside this exact package:**

- Patched `sdDongle`: `0e63050bdd63bebb0d14f8f751b1e920f2679da375b0498a1ace06a2ba376039`
- Experimental `libSdH.so`: `6e70f606501354267567873ec75d291914a5f946a04be3730dc4f085575d1bd9`

The manifest records the SHA-256 for the complete archive; `step147_validate_experimental_package.py` verifies all six ELF payloads and the archive hash **again** on the Mac before any device request.

## 2. Safe final pre-upload probe

Park the vehicle, leave the dongle powered via a stable USB source, and connect the Mac to the dongle's `SmartBox_XXXX` Wi-Fi. From the same repository:

```bash
python3 scripts/step147_flash_experimental.py --probe
```

This verifies the exact experimental archive, both expected device version fields and AK3918AN/Suding identity. It issues **one GET only**, to `http://192.168.200.1/cgi-bin/getversion.cgi`, without redirects or proxies, and sends no archive chunks. Expect `PASS: STEP147 PROBE ONLY — no firmware uploaded or flashed`. If this fails, **do not install**.

## 3. Deliberate firmware installation — writes to dongle

**Only if willing to risk an unbootable adapter:**

```bash
python3 scripts/step147_flash_experimental.py --install
```

The dedicated installer repeats the local SHA-256/tar checks and device identity check **before uploading**. It then explains the permanent-brick risk and requires typing this exact phrase locally:

```text
FLASH STREAM111 AT MY RISK
```

Only after the phrase is entered does it use the historical Suding upload wire protocol: POST 10,240-byte chunks to `downfile.cgi` using CGI receiver name `ak_hook`, require the final `file check success` response, then call the `submition.cgi` installation endpoint and the historical reboot endpoint. The **disk archive remains named `ak_hook_step128_test.tar`**; `ak_hook` is only the legacy CGI receiver name required by its protocol.

Never run the old `python3 flash_ak.py` for this test: it would install the **different historical** `ak_hook.tar`. Do not run `flash_ak.py --check-only` either; it still uploads firmware chunks. If the dedicated installer reports an error **after any upload starts**, do not blindly rerun it; preserve the output to determine whether the target partially accepted the upload.

## 4. First powered test after reboot

With the car parked and the dongle powered continuously:

1. Confirm the device comes back on Wi-Fi and wireless CarPlay can connect to the Audi MMI.
2. Open a map/navigation display and select the Virtual Cockpit map/CarPlay view.
3. Note whether the Lukadev placeholder remains, video appears, an incorrect image appears, or CarPlay crashes/disconnects.
4. If the normal diagnostics remain accessible, preserve `altscreen.log` and regular dongle logs to identify the earliest missing event: stream-111 SETUP, `alt dataPort`, phone accepted, `alt showUI err`, `alt force keyframe err`, incoming frames/IDR, `alt config sent`, and `alt frames pushed`. Do not assume a hardcoded video port 6031; record the negotiated port.
5. Avoid logging sensitive pairing keys/tokens in public issues.

If the dongle still serves its normal Wi-Fi and CGI endpoint, the repository's historical stock restore command is:

```bash
python3 flash_ak.py --stock
```

This does **not** recover a device that cannot boot far enough to serve HTTP. Preserve stable power until reboot completes. The historical installer has its own interactive `yes` confirmation.

## Gate after Step 147

A successful **build + probe** prepares a reproducible experiment but does not change the dongle. A successful **install** is only established after the dongle reports upload/install status and actually reboots; functionality must then be assessed from live video/log evidence. A successful host CI job neither flashes nor validates the car. This entire step leaves `main` and verified original artifacts unchanged.
