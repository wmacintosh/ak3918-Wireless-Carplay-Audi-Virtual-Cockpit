#!/usr/bin/env python3
import hashlib, os, struct, subprocess, tarfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "extracted")
DST = os.path.join(ROOT, "modified")
SHIM_C = os.path.join(ROOT, "altscreen.c")
SHIM_SO = "libSdH.so"
LIBS = ["libSdAuto.so", "libSdCommon.so", "libSdSampleRate.so", "libSdUtils.so"]

BASE_VA = 0x10000
SETUP_VA = 0x0006a60c
HOOK_PTR_VA = 0x001369fc  # Unused 4-byte tail at end of .got (file offset 0x1169fc)

ALTSCREEN_PATCHES = [
    (0x03b43c, 0x0a000002, 0xea000002, "nostrip: keep all displays in /info"),
    (0x03c2e0, 0x1a000009, 0xea000009, "enabledFeatures: always create array"),
    (0x03c364, 0x0a000012, 0xe1a00000, "enabledFeatures: always append viewAreas"),
    (0x03c3c4, 0x0a000005, 0xe1a00000, "enabledFeatures: always take cornerMasks slot"),
    (0x03c678, 0x000bbfc6, 0x000b6d95, "cornerMasks slot -> altScreen CFL (0xf34ea)"),
]

def validate_uclibc_hook(path):
    """Fail closed unless the hook declares the same uClibc soname as sdDongle."""
    import shutil
    if not shutil.which("readelf"):
        raise SystemExit("readelf is required for ELF validation")
    def inspect(*args):
        return subprocess.check_output(["readelf", *args, path], text=True)
    header, dynamic, attributes = inspect("-h"), inspect("-d"), inspect("-A")
    if "Machine:                           ARM" not in header or "ELF32" not in header:
        raise SystemExit("hook must be ELF32 ARM")
    if "soft-float ABI" not in header:
        raise SystemExit("hook must use ARM soft-float ABI")
    if 'Shared library: [libc.so.0]' not in dynamic:
        raise SystemExit("hook must link to uClibc libc.so.0 (musl libc.so is NOT allowed)")
    if "Tag_ABI_VFP_args: VFP registers" in attributes:
        raise SystemExit("hook uses hard-float function calling convention")
    if 'Library soname: [libSdH.so]' not in dynamic:
        raise SystemExit("hook SONAME must be libSdH.so")
    symbols = inspect("-sW")
    if "shim_session_setup" not in symbols:
        raise SystemExit("hook missing shim_session_setup")
    if not any("INIT_ARRAY" in l for l in dynamic.splitlines()):
        raise SystemExit("hook missing constructor initialization array")
    print("PASS: ELF32 ARM, soft float, uClibc dependency, constructor, exported hook")

def build_shim(out):
    """Require an ARM uClibc GCC toolchain with matching target headers/libs."""
    import shlex, shutil
    compiler = os.environ.get("AK_UCLIBC_CC")
    if not compiler:
        raise SystemExit(
            "AK_UCLIBC_CC is unset. Supply the path to an ARMv5TE/uClibc "
            "cross-compiler (with matching sysroot). Refusing musl build."
        )
    command = shlex.split(compiler)
    if not command or not shutil.which(command[0]):
        raise SystemExit("ARM uClibc compiler not found: " + str(compiler))
    # Do not use -nostdlib: the target compiler must select its native uClibc.
    subprocess.run(command + [
        "-mcpu=arm926ej-s", "-mfloat-abi=soft", "-shared", "-fPIC", "-Os",
        "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
        "-Wl,-soname," + SHIM_SO,
        "-o", out, SHIM_C, "-lpthread",
    ], check=True)
    validate_uclibc_hook(out)

def elf_sections(d):
    shoff = struct.unpack_from("<I", d, 0x20)[0]
    she, shn, shstr = struct.unpack_from("<HHH", d, 0x2e)
    base = struct.unpack_from("<6I", d, shoff + shstr * she)[4]
    out = {}
    for i in range(shn):
        nm, ty, fl, ad, off, sz = struct.unpack_from("<6I", d, shoff + i * she)
        name = d[base + nm : d.index(b"\0", base + nm)].decode()
        out[name] = (ad, off, sz)
    return out

def dyn_offsets(d):
    phoff = struct.unpack_from("<I", d, 0x1c)[0]
    n = struct.unpack_from("<H", d, 0x2c)[0]
    for i in range(n):
        t, o, va, pa, fs, ms, fl, al = struct.unpack_from("<8I", d, phoff + i * 32)
        if t == 2:
            return o, fs
    raise SystemExit("no PT_DYNAMIC")

def find_aligned_zero_gap(d, secs, need):
    ad, off, sz = secs[".rodata"]
    run = 0
    start = 0
    for i in range(sz):
        if d[off + i] == 0:
            if run == 0:
                start = i
            run += 1
            # Ensure 4-byte alignment + 4 bytes safety margin
            aligned_start = (start + 3) & ~3
            if (start + run) - aligned_start >= need + 4:
                gva = ad + aligned_start
                return gva, off + aligned_start
        else:
            run = 0
    raise SystemExit("no zero gap in .rodata")

def patch_sddongle(src, dst):
    d = bytearray(open(src, "rb").read())

    # Verify CFL_altScreen at 0xf34ea (file 0xe34ea)
    cfl = bytes(d[0xe34ea : 0xe34ea + 18])
    if cfl != b"\x56\x07\x01\x00\xff\xff\xff\x7faltScreen\x00":
        raise SystemExit(f"altScreen CFL not at file 0xe34ea: {cfl!r}")

    # Apply the 5 altScreen patches
    for va, old, new, what in ALTSCREEN_PATCHES:
        po = va - BASE_VA
        w = struct.unpack_from("<I", d, po)[0]
        if w == new:
            print(f"already patched @{va:#x} ({what})")
        elif w == old:
            struct.pack_into("<I", d, po, new)
            print(f"patched @{va:#x} {old:#010x}->{new:#010x} ({what})")
        else:
            raise SystemExit(f"unexpected word @{va:#x}: {w:#x} ({what})")

    secs = elf_sections(d)
    dynstr_va = secs[".dynstr"][0]
    s = b"libSdH.so\x00$ORIGIN\x00"
    # Need 12 bytes for ARM PLT trampoline + len(s) for DT_NEEDED/RUNPATH strings
    tramp_va, tramp_off = find_aligned_zero_gap(d, secs, 12 + len(s))

    # 1. Initialize writable hook pointer slot at HOOK_PTR_VA (0x1369fc -> file 0x1169fc) to SETUP_VA
    hook_file_off = 0x116000 + (HOOK_PTR_VA - 0x136000)
    struct.pack_into("<I", d, hook_file_off, SETUP_VA)
    print(f"initialized hook slot @{HOOK_PTR_VA:#x} (file {hook_file_off:#x}) = {SETUP_VA:#x}")

    # 2. Write 12-byte ARM trampoline at tramp_va:
    #    e59fc000  ldr ip, [pc, #0]
    #    e59cf000  ldr pc, [ip]
    #    001369fc  .word HOOK_PTR_VA
    struct.pack_into("<3I", d, tramp_off, 0xe59fc000, 0xe59cf000, HOOK_PTR_VA)
    print(f"wrote ARM trampoline @{tramp_va:#x} (file {tramp_off:#x})")

    # 3. Redirect BL at 0x05ec50 (was eb002e6d -> bl 0x6a60c) to tramp_va
    call_va = 0x05ec50
    call_off = call_va - BASE_VA
    old_bl = 0xeb002e6d
    new_bl = 0xeb000000 | (((tramp_va - (call_va + 8)) >> 2) & 0xffffff)
    cur_bl = struct.unpack_from("<I", d, call_off)[0]
    if cur_bl in (old_bl, new_bl):
        struct.pack_into("<I", d, call_off, new_bl)
        print(f"patched Setup BL @{call_va:#x}: {cur_bl:#010x} -> {new_bl:#010x} (trampoline {tramp_va:#x})")
    else:
        raise SystemExit(f"unexpected word @{call_va:#x}: {cur_bl:#x}")

    # 4. Write "libSdH.so\0$ORIGIN\0" right after the 12-byte trampoline
    str_va = tramp_va + 12
    str_off = tramp_off + 12
    d[str_off : str_off + len(s)] = s
    off_needed = str_va - dynstr_va
    off_runpath = (str_va + len(b"libSdH.so\x00")) - dynstr_va
    print(f"strings @{str_va:#x} NEEDED off={off_needed:#x} RUNPATH off={off_runpath:#x}")

    dynoff, dynsz = dyn_offsets(d)
    ents = [list(struct.unpack_from("<iI", d, dynoff + j * 8)) for j in range(dynsz // 8)]
    nulls = [j for j, e in enumerate(ents) if e[0] == 0]
    if len(nulls) < 3:
        raise SystemExit("not enough DT_NULL slots")
    struct.pack_into("<iI", d, dynoff + nulls[0] * 8, 1, off_needed)
    struct.pack_into("<iI", d, dynoff + nulls[1] * 8, 29, off_runpath)
    print(f"injected DT_NEEDED + DT_RUNPATH into slots {nulls[0]},{nulls[1]}")

    open(dst, "wb").write(d)
    print("sdDongle md5", hashlib.md5(d).hexdigest())

def make_tar(outdir):
    tar = os.path.join(ROOT, "ak_hook.tar")
    order = LIBS + ["sdDongle", SHIM_SO]
    with tarfile.open(tar, "w", format=tarfile.GNU_FORMAT) as t:
        for f in order:
            p = os.path.join(outdir, f)
            os.chmod(p, 0o777)
            ti = t.gettarinfo(p, arcname=f)
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            with open(p, "rb") as fh:
                t.addfile(ti, fh)
    print("wrote", tar, os.path.getsize(tar), "md5", hashlib.md5(open(tar, "rb").read()).hexdigest())

def main():
    os.makedirs(DST, exist_ok=True)
    for f in LIBS:
        open(os.path.join(DST, f), "wb").write(open(os.path.join(SRC, f), "rb").read())
    build_shim(os.path.join(DST, SHIM_SO))
    patch_sddongle(os.path.join(SRC, "sdDongle"), os.path.join(DST, "sdDongle"))
    from repair_elf import repair
    print("relocated dynamic string table", repair(os.path.join(DST, "sdDongle")))
    make_tar(DST)

if __name__ == "__main__":
    main()
