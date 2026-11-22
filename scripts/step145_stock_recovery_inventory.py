#!/usr/bin/env python3
"""Step 145: OFFLINE stock recovery archive hardware/boot marker inventory.

No network, no on-device reads, no firmware execution/patch/packaging/flash,
and no extraction to the filesystem. All output is limited to an allowlisted
set of short marker labels and counts, never arbitrary strings/secrets.
Embedded strings only mean the vendor binary mentions a term: they do not
prove that hardware has the identified peripheral or a usable recovery mode.
"""
from collections import OrderedDict
from pathlib import Path
import hashlib
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from step141_readonly_firmware_preflight import (
    RECOVERY_NAME, RECOVERY_SHA256, STOCK_SHA256, REQUIRED_MEMBERS,
    audit_recovery_archive, require,
)

# Exact byte literals only. Keep this deliberately small and auditable:
# never search arbitrary regex contexts, serial numbers, MACs or credentials.
MARKERS = OrderedDict([
    ("AK3918AN", (b"AK3918AN",)),
    ("AK3918AV130", (b"AK3918AV130",)),
    ("AK3918EV200", (b"AK3918EV200",)),
    ("Anyka branding", (b"Anyka", b"ANYKA")),
    ("Suding branding", (b"suding",)),
    ("V851SE alias", (b"v851se", b"V851SE")),
    ("Yunlian alias", (b"yunlian", b"Yunlian")),
    ("AnyCloud alias", (b"anycloud", b"AnyCloud")),
    ("U-Boot label", (b"U-Boot", b"U-BOOT", b"u-boot")),
    ("Bootargs token", (b"bootargs",)),
    ("MTD proc node", (b"/proc/mtd",)),
    ("MTD block node", (b"/dev/mtdblock",)),
    ("MTD char node", (b"/dev/mtd",)),
    ("Anyka tty label", (b"ttySAK",)),
    ("UART term", (b"UART", b"uart")),
    ("SPI-NOR term", (b"spi-nor", b"SPI-NOR", b"spi_nor")),
    ("Recovery term", (b"recovery", b"Recovery")),
    ("Kernel cmdline", (b"/proc/cmdline",)),
    ("Loader path", (b"/lib/ld-uClibc.so.0",)),
    ("libc path", (b"/lib/libc.so.0",)),
])

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as inp:
        for block in iter(lambda:inp.read(256*1024),b""):
            h.update(block)
    return h.hexdigest()


def audit_archive(path, archive_sha=RECOVERY_SHA256, stock_sha=STOCK_SHA256):
    path=Path(path)
    require(path.is_file(),"recovery archive file missing")
    require(sha(path)==archive_sha,"pinned recovery tar SHA-256 mismatch")
    originals=audit_recovery_archive(path,archive_sha)
    require(originals["sdDongle"]==stock_sha,
            "original sdDongle differs from expected pinned SHA-256")
    counts={name:{label:0 for label in MARKERS} for name in REQUIRED_MEMBERS}
    sizes={}
    with tarfile.open(path,"r:*") as tar:
        members={m.name.removeprefix("./"):m for m in tar.getmembers()}
        require(set(members)==set(REQUIRED_MEMBERS),
                "archive unexpectedly has additional members; not a five-file app restore")
        for name in REQUIRED_MEMBERS:
            m=members[name]
            require(m.isfile(),"nonregular archive member")
            sizes[name]=m.size
            inp=tar.extractfile(m)
            require(inp is not None,"cannot read expected stock archive member")
            blob=inp.read()
            require(len(blob)==m.size,"truncated original archive member")
            for label,variants in MARKERS.items():
                counts[name][label]=sum(blob.count(needle) for needle in variants)
    return counts,sizes,originals


def report(path=ROOT/RECOVERY_NAME):
    print("STEP 145 OFFLINE VERIFIED-STOCK HARDWARE/RECOVERY MARKER INVENTORY")
    print("NO DEVICE, NETWORK, FIRMWARE BUILD, PACKAGE, FLASH OR TAR EXTRACTION")
    try:
        counts,sizes,hashes=audit_archive(path)
        print("PASS: original historical tar and all five member hashes verified")
        print(f"ARCHIVE={RECOVERY_NAME}")
        print(f"ARCHIVE_SHA256={RECOVERY_SHA256}")
        print("PACKAGE_SCOPE=five application/vendor ELF files only")
        print("PACKAGE_NOT_PRESENT=full rootfs, kernel, bootloader, board DTB, system libc, target ld-uClibc")
        for name in REQUIRED_MEMBERS:
            labels=[f"{label}={n}" for label,n in counts[name].items() if n>0]
            print(f"MEMBER {name} bytes={sizes[name]} sha256={hashes[name]}")
            print("  EMBEDDED_STRING_MARKER_COUNTS: "+("; ".join(labels) if labels else "(none in allowlist)"))
        print("NOTE: embedded-string mentions are NOT verified PCB identifiers, bootloader access, or runtime libraries")
        print("NOTE: this archive has NO bootloader image or board-specific fullflash recovery payload")
        print("UNKNOWN: exact live flash chip, UART pads, bootloader procedure and on-device libc/loader")
        print("BLOCKED FOR FLASH: out-of-band unbrick and target loader remain unverified")
        print("PASS: STEP145 OFFLINE ARCHIVE-SCOPE INVENTORY")
        return 0
    except (ValueError,OSError,tarfile.TarError) as exc:
        print("FAIL CLOSED: STEP145 ARCHIVE AUDIT:",exc)
        return 2


if __name__=="__main__":
    sys.exit(report())
