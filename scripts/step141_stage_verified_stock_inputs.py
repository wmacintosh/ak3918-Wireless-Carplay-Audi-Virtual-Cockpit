#!/usr/bin/env python3
"""Stage verified original AK3918 build inputs from the pinned recovery tar.

This is an explicit LOCAL filesystem staging action, NOT the read-only preflight.
It cannot package, execute, upload or flash a firmware image; it never modifies
the recovery tar, stock analysis copy or any existing input.

Run from repo: python3 scripts/step141_stage_verified_stock_inputs.py
"""
import hashlib
import os
from pathlib import Path
import sys
import tarfile
import tempfile

import step141_readonly_firmware_preflight as gate


def stage(root, expected_recovery_sha=gate.RECOVERY_SHA256,
          expected_stock_sha=gate.STOCK_SHA256):
    archive = root / gate.RECOVERY_NAME
    # Validate exact archive SHA, member uniqueness/path/link rules, all member
    # presence and member bytes BEFORE creating any outputs.
    expected = gate.audit_recovery_archive(archive, expected_recovery_sha)
    gate.require(expected["sdDongle"] == expected_stock_sha,
                 "pinned recovery archive contains a different sdDongle ELF")
    output = root / "extracted"
    gate.require(not output.is_symlink(),
                 "extracted is a symlink; refusing to follow it")
    gate.require(not output.exists() or output.is_dir(),
                 "extracted exists but is not a directory")
    needed = []
    for name in gate.REQUIRED_MEMBERS:
        target = output / name
        gate.require(not target.is_symlink(),
                     f"existing extracted/{name} is a symlink")
        if os.path.lexists(target):
            gate.require(target.is_file(),
                         f"existing extracted/{name} is not a regular file")
            gate.require(gate.sha256(target) == expected[name],
                         f"existing extracted/{name} differs from verified stock; "
                         "refusing overwrite")
        else:
            needed.append(name)
    if not needed:
        return (), expected

    # Stage only the five named ordinary archive members, not a recursive tar
    # extraction. Every byte is hashed after staging, before publication.
    with tempfile.TemporaryDirectory(prefix=".ak3918-stock-stage-",dir=root) as tmp:
        staged = Path(tmp)
        with tarfile.open(archive,"r:*") as tar:
            for name in needed:
                member = next(m for m in tar.getmembers()
                              if m.name.removeprefix("./") == name and m.isfile())
                fp = tar.extractfile(member)
                gate.require(fp is not None,f"cannot read recovery tar member {name}")
                target = staged / name
                digest=hashlib.sha256()
                with target.open("xb") as out:
                    for chunk in iter(lambda:fp.read(256*1024),b""):
                        digest.update(chunk)
                        out.write(chunk)
                gate.require(digest.hexdigest() == expected[name],
                             f"archive member changed during staging: {name}")

        # mkdir is only reached AFTER verification. os.link is a no-clobber
        # operation: a pre-existing input is NEVER overwritten.
        output.mkdir(exist_ok=True)
        created = []
        try:
            for name in needed:
                os.link(staged/name, output/name)
                created.append(name)
        except Exception:
            for name in created:
                (output/name).unlink()
            raise
    return tuple(needed), expected


def main():
    root=Path(__file__).resolve().parents[1]
    print("STEP 141 VERIFIED-STOCK INPUT STAGING (LOCAL ONLY)")
    print("Never overwrites existing inputs, packages firmware or contacts dongle.")
    try:
        names, hashes=stage(root)
        print("PASS: recovery tar SHA256 and all five original member checksums")
        print("PASS: pinned original stock sdDongle SHA256",hashes["sdDongle"])
        if names:
            for n in names:
                print("STAGED: extracted/"+n)
        else:
            print("PASS: original extracted/ inputs already valid; no files changed")
        print("PASS: STEP141 ORIGINAL INPUTS READY; run read-only preflight next")
        return 0
    except (ValueError,OSError,tarfile.TarError) as e:
        print("FAIL CLOSED:",e)
        print("No existing firmware or recovery input was overwritten.")
        return 2


if __name__=="__main__":
    sys.exit(main())
