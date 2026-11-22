#!/usr/bin/env python3
"""Read a candidate CFRuntimeClass record from the exact verified-stock ELF.

Pure read-only ELF32 little-endian ARM program-header translation. This is
unrelocated on-disk content, not a runtime memory dump. A candidate function
pointer does NOT prove the callback identity or that it is ever invoked.
"""
import argparse
from pathlib import Path
import struct
import sys

ELF32_EHDR = struct.Struct("<16sHHIIIIIHHHHHH")
ELF32_PHDR = struct.Struct("<IIIIIIII")
PT_LOAD = 1
EM_ARM = 40


def read_image(blob: bytes, address: int, count: int) -> tuple[bytes | None, str]:
    if len(blob) < ELF32_EHDR.size:
        raise ValueError("truncated ELF header")
    (ident, _type, machine, _version, _entry, phoff, _shoff, _flags,
     _ehsize, phentsize, phnum, _shentsize, _shnum, _shstrndx) = ELF32_EHDR.unpack_from(blob)
    if ident[:4] != b"\x7fELF" or ident[4] != 1 or ident[5] != 1:
        raise ValueError("expected ELF32 little-endian image")
    if machine != EM_ARM:
        raise ValueError(f"expected ARM machine (40), got {machine}")
    if phentsize < ELF32_PHDR.size or not (1 <= phnum <= 4096):
        raise ValueError("unsupported or empty program header table")
    if phoff + phentsize * phnum > len(blob):
        raise ValueError("truncated program headers")
    for i in range(phnum):
        base = phoff + phentsize * i
        (typ, off, vaddr, _paddr, filesz, memsz, flags, _align) = ELF32_PHDR.unpack_from(blob, base)
        if typ != PT_LOAD or not (vaddr <= address < vaddr + memsz):
            continue
        delta = address - vaddr
        segment = f"LOAD[{i}] vaddr=0x{vaddr:x} fileoff=0x{off:x} filesz=0x{filesz:x} memsz=0x{memsz:x} flags=0x{flags:x}"
        if delta + count > filesz:
            return None, f"{segment}; requested range not file-backed (possibly NOBITS)"
        if off + delta + count > len(blob):
            raise ValueError(f"{segment}: truncated segment bytes")
        return blob[off+delta:off+delta+count], segment
    return None, f"address 0x{address:x} not mapped by a PT_LOAD segment"


def format_descriptor(blob: bytes, addr: int, size: int) -> str:
    chunk, region = read_image(blob, addr, size)
    rows = [
        f"ELF32 ARM on-disk class-descriptor candidate at 0x{addr:08x}",
        f"Program mapping: {region}",
        "This is UNRELOCATED file content. No callback/lifetime conclusion is authorized."
    ]
    if chunk is None:
        rows.append("UNAVAILABLE: candidate class data not present in file-backed load segment.")
        return "\n".join(rows)
    for offset in range(0, len(chunk), 4):
        part = chunk[offset:offset+4]
        if len(part) != 4:
            rows.append(f"  +0x{offset:02x}: {part.hex()} (partial)")
            continue
        value = struct.unpack("<I", part)[0]
        note = "  # potential 32-bit callback slot, must correlate registration ABI and relocations" if offset == 16 else ""
        rows.append(f"  +0x{offset:02x}: 0x{value:08x}{note}")
    return "\n".join(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    p.add_argument("--address", default="0x134e8c", type=lambda s: int(s, 0))
    p.add_argument("--size", default=0x80, type=lambda s: int(s, 0))
    args = p.parse_args()
    if args.size < 4 or args.size > 4096 or args.address < 0:
        p.error("invalid read window")
    try:
        print(format_descriptor(args.elf.read_bytes(), args.address, args.size))
    except (OSError, ValueError) as exc:
        print(f"FAIL: Step 135 class descriptor read: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
