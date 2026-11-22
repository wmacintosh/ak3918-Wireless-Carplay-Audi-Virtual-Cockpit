# Step 143 — Offline loader dependency and independent recovery status

**Status: source-only audit prepared. Mac-side exact ARM/uClibc symbol provider report pending.** This step neither patches nor packages firmware and cannot install it. **No change to `altscreen.c`, `build_hook.py`, stock image, recovery archive, `main`, or device settings.**

## Why this gate is necessary

The [actual Step 142 report](../evidence/AK3918_step142_isolated_elf_audit_uploaded.md) passed its patched ARM ELF and trampoline checks. However, the new library `libSdH.so` contains **DT_BIND_NOW** and **DT_FLAGS_1: NOW**, meaning its required relocations must be resolved during loading. Its undefined dynamic functions include `connect`, `pthread_create`, `pthread_equal`, `pthread_cond_wait`, `pthread_mutex_lock`, `pthread_mutex_unlock`, socket functions, and ordinary libc functions.

That is valid shared-object structure; it is *not* a guarantee the target process can load the library. `libSdH.so` itself declares only `DT_NEEDED=libc.so.0`, not a separate `libpthread.so.0`. This might be correct if the available libc/other already-loaded libraries export pthread symbols. **A genuine symbol-provider inventory is required** before claiming even static compatibility.

The stock `sdDongle` depends on `/lib/ld-uClibc.so.0` and `libc.so.0` and exposes a set of dynamic imports. The archive contains four additional original vendor libraries but **does not include the complete installed target rootfs or bootloader**, so the exact target loader/libc hashes and all actual runtime dependencies cannot be established from this archive alone.

## Available sources and limits

`scripts/step143_audit_loader_symbols.py` reads ELF32 ARM dynamic symbol tables using the same Buildroot cross-`readelf` tool and maintains distinct provider origins:

| Provider | What its symbols can demonstrate | What they cannot demonstrate |
| --- | --- | --- |
| Exact SHA-256-pinned stock `sdDongle` | ELF32 interpreter, original `DT_NEEDED`, exported dynamic symbols | Installed dongle linker/runtime environment |
| Four verified original `libSd*.so` libraries | Exports from the exact vendor-archive members | Other system libraries absent from this archive |
| Buildroot toolchain `libc.so.0` | Whether a *toolchain* uClibc ELF exports requested symbols | That the installed dongle's libc has identical bytes, symbol versions or behavior |
| Buildroot `libpthread.so.0`, if present | Whether a *toolchain* separate pthread library could provide those symbols | Whether that dependency is installed or loaded by the actual dongle |
| Fresh, ephemeral `libSdH.so` | Strong vs weak dynamic imports, exported shim hooks, SONAME, `DT_NEEDED`, BIND_NOW | That native hook constructors are safe or that target relocations succeed |

A successfully matched *name* is a **symbol-availability check** only. ELF symbol versions and actual relocation order may still matter; version normalization for this audit deliberately does **not** claim version compatibility. An unknown import is a **fail-closed static gate**, though it might be resolved by an additional target library not contained in the available sources. No report from this step can establish actual target load success.

## Independent recovery: current evidence

The historical `flash_ak.py` is **not** a robust backup plan for a dongle that fails to boot or expose the network. It checks `/cgi-bin/getversion.cgi`, uploads image chunks through `/cgi-bin/downfile.cgi`, and on a normal flash uses `/cgi-bin/submition.cgi` and `/cgi-bin/reboot.cgi`. **Even `--check-only` calls the chunk uploader**; it skips installation but is **not** a read-only endpoint probe.

`scripts/step143_recovery_readiness.py` verifies that flow **offline** by inspecting the source and rechecking the historical tar's exact pinned hash and stock ELF member. It never contacts the dongle or runs the installer.

There is **no demonstrated out-of-band unbrick procedure** in the supplied project materials. Before risking an installation that might prevent CGI startup, a separate physical recovery plan would need grounded evidence for the dongle's **specific board revision** and firmware layout—for example, identified serial debug interface and bootloader recovery method or a known-good full flash dump plus validated restore tooling. Do not assume that a generic AK3918 UART/JTAG procedure applies to this board; do not erase NAND/flash or write a guessed image.

## Mac command — offline and no firmware patch

```bash
cd "$HOME/AK3918_GitHub"
git pull --ff-only
set -o pipefail
bash scripts/step143_isolated_loader_audit.sh
```

The complete result is written to:

`~/Desktop/AK3918_step143_loader_recovery_audit.txt`

The host wrapper first repeats the original Step 141 input gate, then examines the old CGI updater and recovery archive **without network access**. It starts Docker with `--network none`, the repo and Buildroot volumes mounted **read-only**, compiles a `libSdH.so` in a temporary container workspace with combined stream 111 and phone commands both enabled, and uses cross-`readelf` to compare its strong imports to original and toolchain symbol providers.

**It does not call** `build_hook.patch_sddongle`, `repair_elf`, `make_tar`, `flash_ak.py`, a CGI endpoint, or any target runtime. The temporary ARM library is deleted at container exit. Only the text report is retained on the Mac.

Expected successful endings:

```text
PASS: STEP143 OFFLINE RECOVERY LIMITATION AUDIT
PASS: STEP143 AVAILABLE-PROVIDER ELF SYMBOL AUDIT
PASS: STEP143 OFFLINE SYMBOL AND CGI AUDITS COMPLETE
```

If any required available symbol is not resolved, the script prints `UNKNOWN` and **fails closed**, without implying the physical device lacks that symbol. No software/firmware patch is justified by an incomplete local provider inventory. The script keeps out-of-band recovery and real target loader behavior marked **BLOCKED FOR FLASH** even after a static PASS.

## Follow-up

Review the complete Mac report for unresolved strong symbols and the source of each pthread symbol (stock vs Buildroot libc/pthread). Depending on what the *original vendor* and toolchain libraries actually export, a later **read-only** target-library inventory may be needed to check exact installed libc and loader identity. Do not present a successfully compiled ARM object, a static matched symbol name, or a reachable firmware update CGI as proof the experimental flash is recoverable.
