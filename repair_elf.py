#!/usr/bin/env python3
"""Relocate AK3918 sdDongle .dynstr into a new mapped region without changing VAs.

Raises on unexpected layout; intended for the specific stock AK3918 firmware.
Static ELF repair only: DOES NOT establish runtime safety or libc compatibility.
"""
import struct
from pathlib import Path

U16=lambda b,o:struct.unpack_from('<H',b,o)[0]
U32=lambda b,o:struct.unpack_from('<I',b,o)[0]
P32=lambda b,o,v:struct.pack_into('<I',b,o,v)

def repair(path):
    path=Path(path); d=bytearray(path.read_bytes())
    if d[:6]!=b'\x7fELF\x01\x01' or U16(d,18)!=40:
        raise ValueError('expected little endian ELF32 ARM')
    phoff=U32(d,28); phnum=U16(d,44); phentsz=U16(d,42)
    shoff=U32(d,32); shnum=U16(d,48); shentsz=U16(d,46); shstrndx=U16(d,50)
    if phentsz!=32 or shentsz!=40: raise ValueError('unexpected header sizes')
    shnamesoff=U32(d,shoff+shstrndx*shentsz+16)
    def secname(i):
        no=U32(d,shoff+i*shentsz)
        return d[shnamesoff+no:d.index(0,shnamesoff+no)].decode()
    sections={secname(i):i for i in range(shnum)}
    if '.dynstr' not in sections: raise ValueError('missing dynstr')
    di=sections['.dynstr']; shbase=shoff+di*shentsz
    old_va=U32(d,shbase+12); old_off=U32(d,shbase+16); old_sz=U32(d,shbase+20)
    if old_va!=0x13d04 or old_sz!=12106: raise ValueError('unexpected firmware dynstr layout')
    oldstr=bytes(d[old_off:old_off+old_sz])
    add=b'libSdH.so\x00$ORIGIN\x00'
    newstr=oldstr+add
    insert_off=0x113434
    delta=0x10000  # preserve 64KB PT_LOAD congruence for data segment
    if len(newstr)>delta: raise ValueError('string table too large')
    loads=[]; dynph=None
    for i in range(phnum):
        po=phoff+i*phentsz; ty=U32(d,po)
        if ty==1: loads.append(po)
        if ty==2: dynph=po
    if len(loads)!=2 or dynph is None or U32(d,loads[0]+16)!=insert_off:
        raise ValueError('unexpected program segment layout')
    first=loads[0]; second=loads[1]
    new_va=U32(d,first+8)+insert_off-U32(d,first+4)
    if new_va+len(newstr)>U32(d,second+8): raise ValueError('new mapping overlaps RW segment')
    # Insert entire aligned file block before second segment, keeping all original VAs.
    d[insert_off:insert_off]=newstr+bytes(delta-len(newstr))
    # Expand first LOAD to include relocated dynstr (not the entire padding).
    P32(d,first+16,U32(d,first+16)+len(newstr))
    P32(d,first+20,U32(d,first+20)+len(newstr))
    # Any phdr with original file offset after insertion gets the matching shift.
    for i in range(phnum):
        po=phoff+i*phentsz
        old=U32(d,po+4)
        if old>=insert_off and U32(d,po)!=0:
            P32(d,po+4,old+delta)
    # The section header table lives after the inserted block.
    P32(d,32,shoff+delta)
    for i in range(shnum):
        po=shoff+delta+i*shentsz
        old=U32(d,po+16)
        if old>=insert_off and U32(d,po+4)!=8: # NOBITS has no file contents
            P32(d,po+16,old+delta)
    # Point the .dynstr section at the new region.
    di_off=shoff+delta+di*shentsz
    P32(d,di_off+12,new_va)
    P32(d,di_off+16,insert_off)
    P32(d,di_off+20,len(newstr))
    # Update PT_DYNAMIC entries (dynamic file offset already shifted).
    dynoff=U32(d,dynph+4); dynsz=U32(d,dynph+16)
    needed_off=old_sz; runpath_off=old_sz+len(b'libSdH.so\x00')
    found=[]
    for k in range(dynsz//8):
        pos=dynoff+k*8; tag=U32(d,pos)
        if tag==5: P32(d,pos+4,new_va); found.append('STRTAB')
        elif tag==10: P32(d,pos+4,len(newstr)); found.append('STRSZ')
        elif tag==1 and U32(d,pos+4)==0xef17c:
            P32(d,pos+4,needed_off); found.append('NEEDED')
        elif tag==29 and U32(d,pos+4)==0xef186:
            P32(d,pos+4,runpath_off); found.append('RUNPATH')
    if sorted(found)!=sorted(['STRTAB','STRSZ','NEEDED','RUNPATH']):
        raise ValueError(f'dynamic entry mismatch: {found}')
    path.write_bytes(d)
    return {'new_dynstr_va':hex(new_va),'new_dynstr_size':len(newstr),'file_size':len(d)}

if __name__=='__main__':
    import sys
    print(repair(sys.argv[1]))
