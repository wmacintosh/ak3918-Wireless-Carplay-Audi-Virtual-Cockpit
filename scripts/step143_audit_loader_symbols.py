#!/usr/bin/env python3
"""Step 143: offline ELF dynsym/provider compatibility (NO execution).

Provider groups remain separate: stock-vendor ELFs from the verified firmware,
and uClibc/pthread from the local Buildroot *toolchain sysroot*. A sysroot
export does not prove the deployed dongle has the identical library. Even a
fully covered symbol table does not prove the actual target loader starts.

This script NEVER loads or runs any ARM ELF, modifies a binary, accesses
network/CGI, or packages/installs firmware.
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys

STOCK_SHA = "b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1"
PTHREAD = ("pthread_create", "pthread_detach", "pthread_equal",
           "pthread_cond_wait", "pthread_cond_broadcast",
           "pthread_mutex_init", "pthread_mutex_destroy",
           "pthread_mutex_lock", "pthread_mutex_unlock", "pthread_self")


def need(condition, msg):
    if not condition:
        raise ValueError(msg)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_symbols(readelf_output):
    """Return sets of strong undefined names, weak undefined and exports.

    Parse readelf --dyn-syms -W only. Never count local symtab entries as
    loader-visible exports. Version-qualified names are compared by base name
    here; exact version acceptance remains a separate runtime verification.
    """
    required, weak, exports = set(), set(), set()
    for line in readelf_output.splitlines():
        fields = line.split()
        if len(fields) < 8 or not fields[0].endswith(":"):
            continue
        if not fields[0][:-1].isdigit() or not re.fullmatch(r"[0-9a-fA-F]+", fields[1]):
            continue
        typ, binding, visibility, ndx = fields[3:7]
        if binding not in ("GLOBAL", "WEAK"):
            continue
        if visibility not in ("DEFAULT", "PROTECTED"):
            continue
        name = fields[7].split("@", 1)[0]
        if not name:
            continue
        if ndx == "UND":
            if binding == "GLOBAL":
                required.add(name)
            else:
                weak.add(name)
        else:
            exports.add(name)
    return required, weak, exports


def parse_needed(dynamic_output):
    return re.findall(r"\(NEEDED\).*?Shared library: \[([^\]]+)\]", dynamic_output)


def parse_soname(dynamic_output):
    match = re.search(r"\(SONAME\).*?Library soname: \[([^\]]+)\]", dynamic_output)
    return match.group(1) if match else None


def readelf(reader, path, *args):
    process = subprocess.run([str(reader), *args, str(path)], capture_output=True,
                             text=True, timeout=30, check=False)
    need(process.returncode == 0,
         f"{path}: readelf {' '.join(args)} failed: {process.stderr.strip()[:300]}")
    return process.stdout


def elf_arm32(reader, path):
    header = readelf(reader,path,"-h")
    need(re.search(r"Class:\s*ELF32",header) is not None and
         re.search(r"Machine:\s*ARM\b",header) is not None,
         f"{path}: expected ELF32 ARM library/executable")
    return header


def evaluate(providers, required):
    """Provider is an ordered mapping from source name to export set."""
    solved, missing = {}, []
    for symbol in sorted(required):
        matches=[src for src, exports in providers.items() if symbol in exports]
        if matches:
            solved[symbol]=matches
        else:
            missing.append(symbol)
    return solved,missing


def run(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader",required=True)
    parser.add_argument("--stock",type=Path,required=True)
    parser.add_argument("--hook",type=Path,required=True)
    parser.add_argument("--vendor",type=Path,action="append",default=[])
    parser.add_argument("--sysroot-libc",type=Path)
    parser.add_argument("--sysroot-pthread",type=Path)
    args=parser.parse_args(argv)
    need(args.stock.is_file() and args.hook.is_file(),"stock/hook file missing")
    need(digest(args.stock)==STOCK_SHA,"verified stock sdDongle digest differs")
    need(len(args.vendor)==4 and len({x.name for x in args.vendor})==4,
         "require exactly the four independently verified stock vendor libraries")
    need({x.name for x in args.vendor}=={
        "libSdAuto.so","libSdCommon.so","libSdSampleRate.so","libSdUtils.so"
    },"unexpected stock vendor libraries")
    reader=args.reader
    for path in [args.stock,args.hook,*args.vendor]:
        elf_arm32(reader,path)
    hook_dynamic=readelf(reader,args.hook,"-dW")
    stock_dynamic=readelf(reader,args.stock,"-dW")
    hook_needed=parse_needed(hook_dynamic)
    need(hook_needed==["libc.so.0"],
         f"unexpected hook DT_NEEDED {hook_needed!r}; require libc.so.0 only")
    need(parse_soname(hook_dynamic)=="libSdH.so",
         "hook SONAME does not match expected libSdH.so")
    need("BIND_NOW" in hook_dynamic and "Flags: NOW" in hook_dynamic,
         "hook startup does not match recorded BIND_NOW relocation model")
    stock_interpreter=readelf(reader,args.stock,"-lW")
    need("/lib/ld-uClibc.so.0" in stock_interpreter,
         "verified stock interpreter is not /lib/ld-uClibc.so.0")
    need("libc.so.0" in parse_needed(stock_dynamic),
         "stock executable does not itself declare libc.so.0")
    print("PASS: ELF32 ARM stock and hook, matching libc.so.0, and startup BIND_NOW")
    print("STOCK DT_NEEDED:",", ".join(parse_needed(stock_dynamic)))
    print("HOOK  DT_NEEDED:",", ".join(hook_needed))
    print("STOCK interpreter: /lib/ld-uClibc.so.0 (metadata only)")
    req,weak,hook_exports=parse_symbols(readelf(reader,args.hook,"--dyn-syms","-W"))
    need(req,"hook strong dynamic undefined symbol table is empty")
    for name in ("shim_session_setup","shim_session_finalize",
                 "shim_screen_ensure_stream","shim_screen_http_send"):
        need(name in hook_exports,f"missing exported hook function {name}")
    print(f"HOOK symbols: {len(req)} strong imports, {len(weak)} weak imports, "
          f"{len(hook_exports)} dynamic exports")
    providers={}
    groups={}
    _,_,stock_exports=parse_symbols(readelf(reader,args.stock,"--dyn-syms","-W"))
    providers["stock:sdDongle"]=stock_exports
    for path in sorted(args.vendor):
        _,_,export=parse_symbols(readelf(reader,path,"--dyn-syms","-W"))
        providers["stock:"+path.name]=export
    print("PASS: loaded exact historical stock executable and vendor .dynsym exports")

    if args.sysroot_libc is None or not args.sysroot_libc.is_file():
        print("UNKNOWN: Buildroot sysroot libc.so.0 was not available; cannot resolve ABI")
    else:
        elf_arm32(reader,args.sysroot_libc)
        _,_,exports=parse_symbols(readelf(reader,args.sysroot_libc,"--dyn-syms","-W"))
        providers["toolchain:libc.so.0"]=exports
        print(f"INFO: toolchain libc.so.0 SHA256 {digest(args.sysroot_libc)} "
              "(NOT verified as installed on dongle)")
    if args.sysroot_pthread is None or not args.sysroot_pthread.is_file():
        print("INFO: Buildroot libpthread.so.0 not found; it may be merged into libc")
    else:
        elf_arm32(reader,args.sysroot_pthread)
        _,_,exports=parse_symbols(readelf(reader,args.sysroot_pthread,
                                         "--dyn-syms","-W"))
        providers["toolchain:libpthread.so.0"]=exports
        print(f"INFO: toolchain libpthread.so.0 SHA256 {digest(args.sysroot_pthread)} "
              "(NOT verified as installed on dongle)")

    solved,missing=evaluate(providers,req)
    print("\nSTRONG DYNAMIC HOOK IMPORT RESOLUTION AGAINST AVAILABLE SYMBOL TABLES:")
    for symbol,where in solved.items():
        print(f"  COVERED {symbol:<32} {'; '.join(where)}")
    for symbol in missing:
        print(f"  UNKNOWN {symbol:<32} not present among supplied provider exports")
    print("\nPTHREAD API COVERAGE:")
    for symbol in PTHREAD:
        if symbol in req:
            providers_for=solved.get(symbol)
            print(f"  {symbol}: "+(", ".join(providers_for) if providers_for else "UNKNOWN"))

    print(f"TOTAL_STRONG_IMPORTS {len(req)}")
    print(f"COVERED_STRONG_IMPORTS {len(solved)}")
    print(f"UNKNOWN_STRONG_IMPORTS {len(missing)}")
    print("SHIM_SHA256",digest(args.hook))
    if missing:
        print("FAIL CLOSED: unresolved symbols among AVAILABLE stock/toolchain providers.")
        print("A missing toolchain export does not prove the actual target lacks the symbol.")
        print("BLOCKED FOR FLASH: actual target libraries and loader not checked.")
        return 2
    print("PASS: STEP143 AVAILABLE-PROVIDER ELF SYMBOL AUDIT")
    print("NOT VERIFIED: actual target libc/pthread hashes, target loader search order, "
          "startup relocations, ARM runtime or independent physical recovery")
    print("BLOCKED FOR FLASH: static symbol availability is not target-loader proof.")
    return 0


if __name__=="__main__":
    try:
        sys.exit(run())
    except (ValueError,OSError,subprocess.TimeoutExpired) as e:
        print("FAIL CLOSED: STEP143 SYMBOL AUDIT:",e)
        sys.exit(2)
