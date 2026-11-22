#!/usr/bin/env python3
"""Source-only negative tests for the LOCAL input staging helper.

All archive inputs are synthetic, never original firmware. No firmware archive
is generated, no patching and no device/network calls occur.
"""
import hashlib
import io
import importlib.util
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location(
    "step141_stage",ROOT/"scripts/step141_stage_verified_stock_inputs.py"
)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NAMES=module.gate.REQUIRED_MEMBERS
STOCK=b"synthetic testing ELF - not for use on any hardware"
MEMBERS={name:(STOCK if name=="sdDongle" else b"synthetic-"+name.encode())
         for name in NAMES}


def fake_archive(root, data=None, *, missing=None, duplicate=None):
    tarpath=root/module.gate.RECOVERY_NAME
    data=data or MEMBERS
    with tarfile.open(tarpath,"w") as tar:
        for name,body in data.items():
            if name==missing:
                continue
            m=tarfile.TarInfo(name)
            m.size=len(body)
            tar.addfile(m,io.BytesIO(body))
            if name==duplicate:
                tar.addfile(m,io.BytesIO(body))
    return hashlib.sha256(tarpath.read_bytes()).hexdigest()


def call(root,recovery):
    return module.stage(root,expected_recovery_sha=recovery,
                        expected_stock_sha=hashlib.sha256(STOCK).hexdigest())


class StagingNegativeControls(unittest.TestCase):
    def test_first_time_stage_only_five_verified_members(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            recovery=fake_archive(root)
            original=(root/module.gate.RECOVERY_NAME).read_bytes()
            staged, digests=call(root,recovery)
            self.assertEqual(set(staged),set(NAMES))
            self.assertEqual(set(p.name for p in (root/"extracted").iterdir()),set(NAMES))
            for name in NAMES:
                self.assertEqual((root/"extracted"/name).read_bytes(),MEMBERS[name])
                self.assertEqual(digests[name],hashlib.sha256(MEMBERS[name]).hexdigest())
            self.assertEqual(original,(root/module.gate.RECOVERY_NAME).read_bytes())

    def test_noop_second_run(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            recovery=fake_archive(root)
            call(root,recovery)
            self.assertEqual(call(root,recovery)[0],())

    def test_preexisting_mismatched_file_does_not_get_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            recovery=fake_archive(root)
            (root/"extracted").mkdir()
            target=root/"extracted"/"sdDongle"
            target.write_bytes(b"old local firmware - must not change")
            with self.assertRaisesRegex(ValueError,"refusing overwrite"):
                call(root,recovery)
            self.assertEqual(target.read_bytes(),b"old local firmware - must not change")
            self.assertEqual([p.name for p in (root/"extracted").iterdir()],["sdDongle"])

    def test_missing_member_rejected_before_directory_created(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            recovery=fake_archive(root,missing="libSdUtils.so")
            with self.assertRaisesRegex(ValueError,"libSdUtils.so"):
                call(root,recovery)
            self.assertFalse((root/"extracted").exists())

    def test_wrong_recovery_sha_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fake_archive(root)
            with self.assertRaisesRegex(ValueError,"SHA256"):
                call(root,"0"*64)
            self.assertFalse((root/"extracted").exists())

    def test_wrong_stock_member_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bad=dict(MEMBERS)
            bad["sdDongle"]=b"wrong stock"
            recovery=fake_archive(root,data=bad)
            with self.assertRaisesRegex(ValueError,"different sdDongle"):
                call(root,recovery)
            self.assertFalse((root/"extracted").exists())

    def test_duplicate_member_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            recovery=fake_archive(root,duplicate="sdDongle")
            with self.assertRaisesRegex(ValueError,"duplicate"):
                call(root,recovery)
            self.assertFalse((root/"extracted").exists())

    def test_output_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            recovery=fake_archive(root)
            outside=root/"outside"
            outside.mkdir()
            (root/"extracted").symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,"symlink"):
                call(root,recovery)
            self.assertEqual(list(outside.iterdir()),[])

    def test_source_prohibits_flash_or_firmware_patch_and_clobber(self):
        src=(ROOT/"scripts/step141_stage_verified_stock_inputs.py").read_text()
        for forbidden in ("builder.main(", "patch_sddongle(", "make_tar(", "post_chunk(",
                          "submition.cgi", "reboot.cgi", "flash_ak(", "os.replace(",
                          "tar.extractall(", "tar.extract("):
            self.assertNotIn(forbidden,src)
        self.assertIn("os.link(staged/name, output/name)",src)
        self.assertIn("gate.audit_recovery_archive",src)
        self.assertIn("gate.require(expected[\"sdDongle\"] == expected_stock_sha",src)


if __name__=="__main__":
    unittest.main(verbosity=2)
