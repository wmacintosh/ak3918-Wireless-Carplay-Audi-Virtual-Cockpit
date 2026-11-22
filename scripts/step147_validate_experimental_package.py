#!/usr/bin/env python3
"""Strict local validator for the Step147 experimental AK3918 stream-111 tar.

Never opens the dongle, executes firmware, uploads data, or modifies the files.
This is NOT a proof of target runtime or unbrick recovery.
"""
import hashlib
import json
from pathlib import Path
import re
import tarfile

PACKAGE_NAME = "ak_hook_step128_test.tar"
MANIFEST_NAME = "step147-manifest.json"
EXPECTED = {
    "libSdAuto.so": "3f44ce2a8f7f81b585fce426747354d59a3f0e71877b638173f542456da2be6b",
    "libSdCommon.so": "36480881ba077fbafa7d1f79767f7f6df8072cb78f7cd009c59c4af4f20722b4",
    "libSdSampleRate.so": "6e1cfdf3a91fdee5bf0a126c122c06ea84fcf1fb4741986b02f47f9ea0de7e14",
    "libSdUtils.so": "6872f533caad8e59d5fdbc3f48e4ef14e315479710f2378b9dea01383fbf876a",
    "sdDongle": "0e63050bdd63bebb0d14f8f751b1e920f2679da375b0498a1ace06a2ba376039",
    "libSdH.so": "6e70f606501354267567873ec75d291914a5f946a04be3730dc4f085575d1bd9",
}
EXPECTED_ORDER = list(EXPECTED)
EXPECTED_BRANCH = "wip/ak3918-step115-callback-tombstones"
EXPECTED_SYSTEM_VERSION = "20260411104900CA"
EXPECTED_PROTOCOL_VERSION = "20261008165915"
MAX_PACKAGE_BYTES = 8 * 1024 * 1024


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate(package, manifest):
    """Return archive bytes and manifest after all exact-match assertions."""
    package,manifest=Path(package),Path(manifest)
    require(package.name == PACKAGE_NAME, "experimental archive name is not exact")
    require(manifest.name == MANIFEST_NAME, "expected dedicated test manifest")
    require(package.is_file() and manifest.is_file(), "missing experimental tar or manifest")
    require(not package.is_symlink() and not manifest.is_symlink(), "symlink package/manifest refused")
    require(0<package.stat().st_size<=MAX_PACKAGE_BYTES, "unexpected archive size")
    require(manifest.stat().st_size<=8192, "oversized test manifest")
    record=json.loads(manifest.read_text())
    require(type(record) is dict, "manifest must be an object")
    require(set(record)=={
        "format","package","sha256","branch","commit","features",
        "system_version","protocol_version","members",
    }, "unexpected manifest fields")
    require(record["format"]=="ak3918-step147-stream111-test-v1","unknown test manifest format")
    require(record["package"]==PACKAGE_NAME,"wrong declared archive name")
    require(record["branch"]==EXPECTED_BRANCH,"wrong source branch")
    require(isinstance(record["commit"],str) and
            re.fullmatch("[0-9a-f]{40}",record["commit"]) is not None,
            "invalid source commit")
    require(record["features"]=={
        "AK_ENABLE_COMBINED_CLUSTER":1,
        "AK_ENABLE_PHONE_CMDS":1,
    },"incorrect experimental feature flags")
    require(record["system_version"]==EXPECTED_SYSTEM_VERSION,
            "unexpected pinned device system version")
    require(record["protocol_version"]==EXPECTED_PROTOCOL_VERSION,
            "unexpected pinned device protocol version")
    require(record["members"]==EXPECTED,
            "manifest ELF/library hashes differ from independently inspected originals")
    blob=package.read_bytes()
    require(record["sha256"]==sha256(blob),"archive SHA-256 differs from test manifest")
    with tarfile.open(fileobj=__import__("io").BytesIO(blob),mode="r:*") as tf:
        members=tf.getmembers()
        require([m.name for m in members]==EXPECTED_ORDER,
                "archive names/order differ from exact six expected ELF files")
        for member in members:
            require(member.isfile() and member.size>0 and
                    member.size<MAX_PACKAGE_BYTES,
                    "unexpected tar entry type or size: "+member.name)
            f=tf.extractfile(member)
            require(f is not None,"unreadable archive member: "+member.name)
            content=f.read()
            require(len(content)==member.size,"truncated tar member "+member.name)
            require(sha256(content)==EXPECTED[member.name],
                    "incorrect original or experimental ELF: "+member.name)
            require(content[:4]==b"\x7fELF",
                    "archive member is not an ELF object: "+member.name)
    return blob,record


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package",type=Path)
    parser.add_argument("manifest",type=Path)
    args=parser.parse_args()
    try:
        tar,record=validate(args.package,args.manifest)
        print("PASS: STEP147 EXACT EXPERIMENTAL STREAM111 TAR AND MANIFEST")
        print("ARCHIVE_SHA256",record["sha256"])
        print("SOURCE_COMMIT",record["commit"])
        print("SIX_VERIFIED_ELF_FILES",len(EXPECTED))
        print("NOT VERIFIED: target runtime or non-Wi-Fi recovery")
    except (OSError,ValueError,tarfile.TarError,json.JSONDecodeError) as exc:
        print("FAIL CLOSED: STEP147 PACKAGE VALIDATION:",exc)
        raise SystemExit(2)
