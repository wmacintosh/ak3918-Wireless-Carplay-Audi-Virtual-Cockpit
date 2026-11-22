#!/usr/bin/env python3
"""Inspect ephemeral Step142 built ELF and ARM/uClibc library.

STRICTLY READ-ONLY. Expects a separate copied build_hook.py in the isolated
Docker workdir; imports it for original constants, ELF mapping helpers only.
This script never executes an ELF or loads the target ARM .so.
"""
import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys

STOCK_SHA="b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1"
INSERT_AT=0x113434
DELTA=0x10000
DYN_APPEND=b"libSdH.so\x00$ORIGIN\x00"


def need(ok,why):
    if not ok:
        raise ValueError(why)


def word(d,at):
    need(at>=0 and at+4<=len(d),"ELF word out of range")
    return struct.unpack_from("<I",d,at)[0]


def arm_bl_dest(va, insn):
    """Decode ARM-state unconditional BL and its signed PC+8 displacement."""
    need(insn & 0xff000000 == 0xeb000000,
         f"expected ARM-state unconditional BL at {va:#x}, got {insn:#010x}")
    value=insn & 0xffffff
    if value & 0x800000:
        value-=1<<24
    return (va+8+(value<<2))&0xffffffff


def mapped_word(builder,blob,va,flags=None):
    if flags is None:
        flags=builder.PF_R
    off=builder.va_to_file_off(blob,va,4,require_flags=flags)
    return word(blob,off)


def elf_header(d,name):
    need(len(d)>=52 and d[:6]==b"\x7fELF\x01\x01",
         f"{name}: not ELF32 little endian")
    need(struct.unpack_from("<H",d,16)[0] in (2,3),
         f"{name}: unsupported ELF type")
    need(struct.unpack_from("<H",d,18)[0]==40,
         f"{name}: not ARM")
    need(struct.unpack_from("<H",d,42)[0]==32,
         f"{name}: invalid program header entry size")


def dynamic(builder,blob):
    off,size=builder.dyn_offsets(blob)
    need(size%8==0 and off+size<=len(blob),"truncated ELF dynamic table")
    records={}
    for index in range(0,size,8):
        tag,val=struct.unpack_from("<iI",blob,off+index)
        if tag==0:
            break
        records.setdefault(tag,[]).append(val)
    return records


def dyn_string(blob,base,index,size):
    need(0<=index<size,"DT string index outside STRSZ")
    start=base+index
    need(start<len(blob),"DT string starts past ELF")
    end=blob.find(b"\x00",start,min(len(blob),base+size))
    need(end>=0,"unterminated dynamic string")
    return blob[start:end]


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def audit(stock_path,patched_path,shim_path,builder):
    old=Path(stock_path).read_bytes()
    new=Path(patched_path).read_bytes()
    shim=Path(shim_path).read_bytes()
    elf_header(old,"original")
    elf_header(new,"patched")
    elf_header(shim,"libSdH.so")
    need(sha(old)==STOCK_SHA,"original stock binary SHA-256 mismatch")
    need(len(new)==len(old)+DELTA,"repaired ELF does not contain expected 64K offset shift")
    need(new[:4]==old[:4],"ELF magic changed")
    need(struct.unpack_from("<H",new,16)[0]==2,"patched ELF is not EXEC")
    need(struct.unpack_from("<H",shim,16)[0]==3,"hook must be DYN/shared object")

    original_sections=builder.elf_sections(old)
    new_sections=builder.elf_sections(new)
    old_dyn=original_sections[".dynstr"]
    new_dyn=new_sections[".dynstr"]
    need(old_dyn[0]==0x13d04 and old_dyn[2]==12106,
         "unexpected original stock .dynstr layout")
    need(new_dyn[2]==old_dyn[2]+len(DYN_APPEND),
         "relocated dynamic string table has unexpected size")
    old_bytes=old[old_dyn[1]:old_dyn[1]+old_dyn[2]]
    new_bytes=new[new_dyn[1]:new_dyn[1]+new_dyn[2]]
    need(new_bytes==old_bytes+DYN_APPEND,
         "relocated .dynstr is not exact stock strings plus hook/runpath")
    need(new_dyn[1]==INSERT_AT,
         "new dynamic string table at unexpected file offset")

    # The patched ELF must have the expected callable setup/screen trampolines,
    # not just modified BL words that branch to arbitrary loaded code.
    addresses=[
        (0x05EC50,0xEB002E6D,0x001369FC,"session setup"),
        (0x02FADC,0xEB018DE6,0x0013C644,"stream-array ensure"),
        (0x02FBB0,0xEB01DB6F,0x0013C648,"HTTP screen send"),
    ]
    trampolines=[]
    for va,original,ptr,name in addresses:
        need(mapped_word(builder,old,va,builder.PF_R|builder.PF_X)==original,
             f"original {name} ARM branch has changed")
        insn=mapped_word(builder,new,va,builder.PF_R|builder.PF_X)
        target=arm_bl_dest(va,insn)
        off=builder.va_to_file_off(new,target,12,builder.PF_R|builder.PF_X)
        words=struct.unpack_from("<3I",new,off)
        need(words==(0xE59FC000,0xE59CF000,ptr),
             f"{name}: unexpected trampoline bytes at {target:#x}: {words!r}")
        need(target%4==0,"unaligned ARM branch target")
        print(f"PASS: {name}: original {va:#x} -> trampoline {target:#x} -> pointer slot {ptr:#x}")
        trampolines.append(target)

    finalizer_original=0x00066A40
    finalizer_cb=0x00134078
    need(mapped_word(builder,old,finalizer_cb,builder.PF_R|builder.PF_W)==finalizer_original,
         "original session finalizer differs")
    finalizer_target=mapped_word(builder,new,finalizer_cb,builder.PF_R|builder.PF_W)
    fin_off=builder.va_to_file_off(new,finalizer_target,12,builder.PF_R|builder.PF_X)
    need(struct.unpack_from("<3I",new,fin_off)==
         (0xE59FC000,0xE59CF000,0x0013C640),
         "session finalizer trampoline does not reference correct slot")
    need(finalizer_target not in trampolines and
         len(set(trampolines))==len(trampolines),
         "trampoline targets overlap or alias")
    print(f"PASS: class finalizer slot {finalizer_cb:#x} -> trampoline {finalizer_target:#x} -> 0x13c640")

    for va,original,updated,_label in builder.ALTSCREEN_PATCHES:
        need(mapped_word(builder,old,va,builder.PF_R|builder.PF_X)==original,
             f"original display patch word mismatch at {va:#x}")
        need(mapped_word(builder,new,va,builder.PF_R|builder.PF_X)==updated,
             f"patched display word mismatch at {va:#x}")
    print("PASS: original five display patches match expected ARM words")

    old_bss=original_sections[".bss"]
    new_bss=new_sections[".bss"]
    need(old_bss[2]==0x1f90 and new_bss[2]==old_bss[2]+12,
         "combined-mode hook pointer space is not 12 bytes")
    need(old_bss[0]==new_bss[0]==0x13a6b0,
         "combined patch unexpectedly relocated .bss")
    print("PASS: BSS size increased by precisely three 32-bit callback slots")

    dyn=dynamic(builder,new)
    for tag in (1,5,10,29):
        need(tag in dyn, f"patched dynamic table lacks required DT tag {tag}")
    need(len(dyn[5])==1 and len(dyn[10])==1 and len(dyn[29])==1,
         "ambiguous ST(RTAB|SZ) / RUNPATH tags")
    need(dyn[5][0]==new_dyn[0] and dyn[10][0]==new_dyn[2],
         "DT_STRTAB/DT_STRSZ do not reference relocated .dynstr")
    str_off=builder.va_to_file_off(new,dyn[5][0],dyn[10][0],builder.PF_R)
    names=[dyn_string(new,str_off,index,dyn[10][0]) for index in dyn[1]]
    runpath=dyn_string(new,str_off,dyn[29][0],dyn[10][0])
    need(names.count(b"libSdH.so")==1,
         f"DT_NEEDED does not list exactly one libSdH.so: {names!r}")
    need(runpath==b"$ORIGIN", f"unexpected dynamic loader RUNPATH {runpath!r}")
    print(f"PASS: relocated DT_STRTAB, DT_NEEDED {names!r} and RUNPATH=$ORIGIN")

    # Header/segment structure, not a loader execution test.
    phoff=word(new,28)
    phnum=struct.unpack_from("<H",new,44)[0]
    loads=[]
    for i in range(phnum):
        typ,offset,vaddr,_paddr,filesz,memsz,flags,alignment=struct.unpack_from(
            "<8I",new,phoff+i*32)
        if typ==1:
            need(filesz<=memsz and offset+filesz<=len(new),
                 "invalid PT_LOAD file/memory size")
            need(alignment and (offset%alignment)==(vaddr%alignment),
                 "patched PT_LOAD offset/VA alignment congruence violated")
            loads.append((vaddr,memsz))
    need(len(loads)==2,"unexpected number of patched PT_LOAD segments")
    loads.sort()
    need(loads[0][0]+loads[0][1]<=loads[1][0],
         "patched PT_LOAD virtual ranges overlap")
    print("PASS: both file-backed PT_LOAD ranges are valid, congruent and nonoverlapping")

    # Native library is not run by this static audit.
    prefix=Path(sys.argv[4])
    readelf=str(prefix)+"-readelf"
    for f in (patched_path,shim_path):
        result=subprocess.run([readelf,"-h",str(f)],text=True,capture_output=True,check=True)
        need("Machine:                           ARM" in result.stdout,
             f"{f} is not ARM according to cross-readelf")
    dynamic_lib=subprocess.run([readelf,"-dW",str(shim_path)],
                               capture_output=True,text=True,check=True).stdout
    symbols=subprocess.run([readelf,"-sW",str(shim_path)],
                           capture_output=True,text=True,check=True).stdout
    need("Shared library: [libc.so.0]" in dynamic_lib,
         "hook missing uClibc dependency")
    need("Library soname: [libSdH.so]" in dynamic_lib,
         "hook SONAME is not libSdH.so")
    for name in ("shim_session_setup","shim_session_finalize",
                 "shim_screen_ensure_stream","shim_screen_http_send",
                 "shim_screen_response"):
        need(name in symbols,f"required hook symbol {name!r} missing")
    need("INIT_ARRAY" in dynamic_lib,"hook missing constructor init array")
    print("PASS: hook ELF32 ARM/uClibc libc.so.0, SONAME, constructor and five native symbols")

    print("ORIGINAL_STOCK_SHA256",sha(old))
    print("PATCHED_ELF_SHA256",sha(new))
    print("LIBSDH_SO_SHA256",sha(shim))
    print("PASS: STEP142 STATIC PATCHED ELF AUDIT")
    print("NOT VERIFIED: actual loader startup, target ABI call safety, native callback concurrency, physical recovery")
    print("BLOCKED FOR FLASH: isolated static build audit is not device deployment authorization")


def import_builder(path):
    spec=importlib.util.spec_from_file_location("step142_builder",path)
    need(spec is not None and spec.loader is not None,
         "builder module unavailable")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    try:
        need(len(sys.argv)==5,"Usage: step142_audit_patched_elf.py stock patched libSdH.so toolchain-prefix")
        # Imported builder only supplies known constants and read-only helpers.
        builder=import_builder(Path(__file__).resolve().parents[1]/"build_hook.py")
        audit(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),builder)
        return 0
    except (OSError,ValueError,struct.error,subprocess.CalledProcessError) as error:
        print("FAIL CLOSED: STEP142 STATIC AUDIT:",error)
        return 2


if __name__=="__main__":
    sys.exit(main())
