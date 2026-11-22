#!/usr/bin/env python3
"""Step 141: OFFLINE, READ-ONLY preflight before experimental firmware review.

Checks pinned stock ELF, original recovery tar, ARM callsites, anticipated
trampoline placement *in memory only*, builder flags and git state. This
script NEVER builds, patches an executable on disk, packages, uploads, flashes,
contacts the dongle, or changes stock/recovery artifacts.

A PASS is a prerequisite for additional review, NOT authorization to flash.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "wip/ak3918-step115-callback-tombstones"
STOCK_SHA256 = "b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1"
RECOVERY_SHA256 = "a4ee31452833cc38cf4a3839adaa75b9b34fd0a9d2ed006e0c9b34ae7539dba3"
RECOVERY_NAME = "stock_ak_202610081659.tar"
REQUIRED_MEMBERS = (
    "libSdAuto.so", "libSdCommon.so", "libSdSampleRate.so",
    "libSdUtils.so", "sdDongle",
)
STOCK_WORDS = {
    0x05EC50: 0xEB002E6D,  # Original session setup hook
    0x02FADC: 0xEB018DE6,  # Original CFArray ensure
    0x02FBB0: 0xEB01DB6F,  # Original HTTPClientSendMessage
}
STOCK_DISPLAY_WORDS = {
    0x03B43C: 0x0A000002,
    0x03C2E0: 0x1A000009,
    0x03C364: 0x0A000012,
    0x03C3C4: 0x0A000005,
    0x03C678: 0x000BBFC6,
}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 256), b""):
            h.update(part)
    return h.hexdigest()


def require(ok, problem):
    if not ok:
        raise ValueError(problem)


def stock_word(blob, builder, va, flags):
    at = builder.va_to_file_off(blob, va, 4, require_flags=flags)
    return struct.unpack_from("<I", blob, at)[0]


def audit_stock_elf(blob, builder):
    """Pure in-memory structural tests. No target image is ever written."""
    require(blob[:6] == b"\x7fELF\x01\x01", "ELF is not little-endian ELF32")
    require(struct.unpack_from("<H", blob, 18)[0] == 40, "ELF e_machine is not ARM")
    require(struct.unpack_from("<H", blob, 16)[0] == 2, "ELF e_type is not EXEC")
    require(hashlib.sha256(blob).hexdigest() == STOCK_SHA256,
            "stock ELF SHA256 differs from pinned verified original")
    for address, word in (STOCK_WORDS | STOCK_DISPLAY_WORDS).items():
        actual = stock_word(blob, builder, address, builder.PF_R | builder.PF_X)
        require(actual == word,
                f"stock ARM word mismatch at 0x{address:x}: "
                f"got 0x{actual:08x}, expected 0x{word:08x}")
    require(blob[0xE34EA:0xE34EA+18] ==
            b"\x56\x07\x01\x00\xff\xff\xff\x7faltScreen\x00",
            "original altScreen CFL differs")
    cls = builder.va_to_file_off(blob, 0x1028B4, 24, require_flags=builder.PF_R)
    require(blob[cls:cls+23].split(b"\x00", 1)[0] == b"AirPlayReceiverSession",
            "AirPlayReceiverSession class name mismatch")
    cb = stock_word(blob, builder, 0x134078, builder.PF_R | builder.PF_W)
    require(cb == 0x66A40, f"stock session finalizer callback mismatch: {cb:#x}")
    sections = builder.elf_sections(blob)
    require(".rodata" in sections and ".bss" in sections, "missing stock ELF section")
    bss, _offset, size = sections[".bss"]
    require((bss, size, bss+size) == (0x13A6B0, 0x1F90, 0x13C640),
            "stock .bss bounds differ: refusing layout assumption")

    p_off = struct.unpack_from("<I", blob, 28)[0]
    p_num = struct.unpack_from("<H", blob, 44)[0]
    p_size = struct.unpack_from("<H", blob, 42)[0]
    require(p_size == 32 and p_off+p_num*p_size <= len(blob),
            "invalid program-header table")
    relro_ok = False
    for i in range(p_num):
        off=p_off+i*p_size
        typ, _, va, _, _, memsz, _, _ = struct.unpack_from("<8I", blob, off)
        if typ == 0x6474E552 and va <= 0x134078 and 0x13407C <= va+memsz:
            relro_ok = True
    require(relro_ok, "stock session finalizer slot not in expected GNU RELRO")
    dyn, nbytes = builder.dyn_offsets(blob)
    require(dyn+nbytes<=len(blob) and nbytes%8==0, "invalid PT_DYNAMIC")
    require(sum(struct.unpack_from("<i",blob,dyn+i)[0]==0
                for i in range(0,nbytes,8))>=3,
            "fewer than 3 dynamic null slots")

    # Mirror the source builder's zero-gap selection, marking only a fresh
    # MEMORY COPY as occupied. This checks four independent executable-mapped
    # candidates (setup, finalizer, screen ensure, HTTP send), without patching
    # either the input blob or filesystem.
    work = bytearray(blob)
    slots=[]
    for desc, size in (
        ("setup trampoline and dynamic strings", 12+len(b"libSdH.so\x00$ORIGIN\x00")),
        ("session finalizer trampoline",12),
        ("combined stream ensure trampoline",12),
        ("combined HTTP send trampoline",12),
    ):
        va, off=builder.find_aligned_zero_gap(work,sections,size)
        checked=builder.va_to_file_off(blob,va,size,
                                       require_flags=builder.PF_R | builder.PF_X)
        require(checked==off, f"{desc} is not executable-mapped")
        require(off%4==0 and va%4==0, f"{desc} not ARM word-aligned")
        require(all(b==0 for b in work[off:off+size]),
                f"{desc} overwrites nonzero stock ELF bytes")
        require(not any(not (off+size <= prev_off or
                            prev_off+prev_size <= off)
                        for _,prev_off,prev_size in slots),
                f"{desc} overlaps another trampoline candidate")
        slots.append((va,off,size))
        work[off:off+size]=b"\xA5"*size

    for src, dest in ((0x5EC50,slots[0][0]),
                      (0x2FADC,slots[2][0]),
                      (0x2FBB0,slots[3][0])):
        displacement=dest-(src+8)
        require(displacement%4==0 and -(1<<25)<=displacement<(1<<25),
                f"ARM BL range/alignment invalid for callsite 0x{src:x}")
    return [(hex(va),hex(off),length) for va,off,length in slots]


def audit_recovery_archive(tar_path, expected_sha=RECOVERY_SHA256):
    require(tar_path.is_file(), f"recovery archive absent: {tar_path}")
    require(sha256(tar_path) == expected_sha,
            "recovery archive SHA256 does NOT match historical pinned copy")
    with tarfile.open(tar_path, "r:*") as tar:
        names = [m.name.removeprefix("./") for m in tar.getmembers()]
        require(len(set(names)) == len(names), "duplicate archive member names")
        require(all(not m.name.startswith("/") and
                    ".." not in Path(m.name).parts and
                    not (m.issym() or m.islnk()) for m in tar.getmembers()),
                "unsafe archive member path/link")
        for name in REQUIRED_MEMBERS:
            matches=[m for m in tar.getmembers()
                     if m.name.removeprefix("./")==name and m.isfile()]
            require(len(matches)==1,
                    f"recovery archive missing or duplicating {name}")
        require(names.count("sdDongle")==1 or names.count("./sdDongle")==1,
                "recovery archive sdDongle member missing")
        result = {}
        for name in REQUIRED_MEMBERS:
            m = next(x for x in tar.getmembers()
                     if x.name.removeprefix("./")==name)
            fh = tar.extractfile(m)
            require(fh is not None, f"cannot inspect recovery {name}")
            result[name] = hashlib.sha256(fh.read()).hexdigest()
        return result


def source_git_status():
    commands = [
        ["git","-C",str(ROOT),"rev-parse","--abbrev-ref","HEAD"],
        ["git","-C",str(ROOT),"rev-parse","--short=12","HEAD"],
        ["git","-C",str(ROOT),"status","--porcelain","--untracked-files=no"],
    ]
    out=[]
    for cmd in commands:
        r=subprocess.run(cmd,check=False,text=True,capture_output=True,timeout=8)
        require(r.returncode==0, "git inspection failed: "+(r.stderr.strip() or "unknown"))
        out.append(r.stdout.strip())
    branch,commit,dirty=out
    require(branch==EXPECTED_BRANCH,
            f"current git branch {branch!r} is not isolated WIP branch")
    require(not dirty,
            "tracked repository files are modified; resolve before preflight: "+dirty[:300])
    return commit


def import_builder():
    # Importing this module only defines functions. The builder's main() is
    # protected by if __name__ == '__main__' and MUST NOT be called here.
    spec=importlib.util.spec_from_file_location("ak3918_readonly_builder",ROOT/"build_hook.py")
    require(spec is not None and spec.loader is not None,"cannot inspect builder")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_requested_flags():
    vars=("AK_ENABLE_COMBINED_CLUSTER","AK_ENABLE_PHONE_CMDS",
          "AK_STEP128_ALLOW_TEST_PACKAGE")
    for k in vars:
        require(os.environ.get(k)=="1",
                f"{k} must be 1 for the experimental test-only build configuration")
    require(os.environ.get("AK_STEP100_ALLOW_UNVERIFIED_PACKAGE")!="1",
            "legacy package mode is forbidden for combined experiment")
    builder=import_builder()
    require(builder.ENABLE_COMBINED_CLUSTER and builder.ENABLE_PHONE_CMDS,
            "builder is not configured for both combined and phone commands")
    require(builder.package_plan()=="ak_hook_step128_test.tar",
            "test-only package naming policy differs")
    return builder


def run():
    print("STEP 141 OFFLINE READ-ONLY EXPERIMENTAL PREFLIGHT")
    print("This script does NOT build, package, upload or flash firmware.")
    try:
        commit=source_git_status()
        print(f"PASS: isolated WIP branch, clean tracked tree, commit {commit}")
        builder=verify_requested_flags()
        print("PASS: combined=1 phone=1, opt-in test-only package plan")
        expected_pinned=ROOT/"extracted"/"sdDongle"
        require(expected_pinned.is_file(),
                "builder input extracted/sdDongle is missing; do not use modified/sdDongle")
        stock=expected_pinned.read_bytes()
        slots=audit_stock_elf(stock,builder)
        print("PASS: exact original ARM stock SHA256 and patch-input invariants")
        for addr,off,length in slots:
            print(f"PASS: in-memory mapped zero-gap candidate VA={addr} file={off} bytes={length}")
        recovery=ROOT/RECOVERY_NAME
        archive_members=audit_recovery_archive(recovery)
        print("PASS: historical recovery archive hash, file names and member safety")
        require(archive_members["sdDongle"]==STOCK_SHA256,
                "recovery archive's sdDongle differs from pinned original")
        for name in REQUIRED_MEMBERS:
            extracted=ROOT/"extracted"/name
            require(extracted.is_file(),
                    f"missing builder library/image input: extracted/{name}")
            require(sha256(extracted)==archive_members[name],
                    f"extracted/{name} differs from matching recovery tar member")
        print("PASS: all five builder inputs equal original recovery archive members")
        flash=(ROOT/"flash_ak.py").read_text()
        require('"stock_ak_202610081659.tar" if stock else "ak_hook.tar"' in flash,
                "historical installer target selection changed")
        print("PASS: historical installer is for stock/legacy tar ONLY, not this experiment")
        cc=os.environ.get("AK_UCLIBC_CC")
        if cc:
            import shlex
            parsed=shlex.split(cc)
            print("INFO: ARM compiler selector present, binary executable lookup: "+
                  str(bool(parsed and shutil.which(parsed[0]))))
        else:
            print("INFO: AK_UCLIBC_CC unset on host; builder requires ARM/uClibc compiler")
        print("PASS: STEP141 OFFLINE STATIC PREFLIGHT")
        print("BLOCKED FOR FLASH: preflight does not validate a final built/repaired ELF, "
              "ARM imports in the target loader, independent recovery if CGI is unavailable, "
              "or actual car runtime.")
        return 0
    except (ValueError,OSError,RuntimeError,tarfile.TarError,
            subprocess.TimeoutExpired) as exc:
        print(f"FAIL CLOSED: {exc}")
        print("NO BUILD, FIRMWARE PACKAGE, UPLOAD OR FLASH WAS ATTEMPTED")
        return 2


if __name__=="__main__":
    sys.exit(run())
