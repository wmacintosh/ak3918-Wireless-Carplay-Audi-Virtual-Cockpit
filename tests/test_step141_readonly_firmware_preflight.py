#!/usr/bin/env python3
"""Step 141 offline preflight: only in-memory/synthetic tests; never flash."""
import hashlib
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/step141_readonly_firmware_preflight.py"
spec=importlib.util.spec_from_file_location("step141_readonly",SCRIPT)
preflight=importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def make_tar(path, content=None, extra=None, link=None):
    content=content or {n:b"stock-"+n.encode() for n in preflight.REQUIRED_MEMBERS}
    with tarfile.open(path,"w") as t:
        for name,data in content.items():
            item=tarfile.TarInfo(name)
            item.size=len(data)
            t.addfile(item,io.BytesIO(data))
        if extra is not None:
            item=tarfile.TarInfo(extra)
            item.size=1
            t.addfile(item,io.BytesIO(b"x"))
        if link is not None:
            item=tarfile.TarInfo("bad_link")
            item.type=tarfile.SYMTYPE
            item.linkname=link
            t.addfile(item)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReadOnlyPreflight(unittest.TestCase):
    def test_required_exact_elf_and_source_words_pinned(self):
        self.assertEqual(preflight.STOCK_SHA256,
                         "b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1")
        self.assertEqual(preflight.RECOVERY_SHA256,
                         "a4ee31452833cc38cf4a3839adaa75b9b34fd0a9d2ed006e0c9b34ae7539dba3")
        self.assertEqual(preflight.STOCK_WORDS,{
            0x5EC50:0xEB002E6D,
            0x2FADC:0xEB018DE6,
            0x2FBB0:0xEB01DB6F,
        })
        self.assertEqual(preflight.STOCK_DISPLAY_WORDS[0x3C678],0x000BBFC6)

    def test_original_build_config_only(self):
        e={"AK_ENABLE_COMBINED_CLUSTER":"1","AK_ENABLE_PHONE_CMDS":"1",
           "AK_STEP128_ALLOW_TEST_PACKAGE":"1"}
        with mock.patch.dict(os.environ,e,clear=True):
            builder=preflight.verify_requested_flags()
            self.assertTrue(builder.ENABLE_COMBINED_CLUSTER)
            self.assertTrue(builder.ENABLE_PHONE_CMDS)
            self.assertEqual(builder.package_plan(),"ak_hook_step128_test.tar")
        with mock.patch.dict(os.environ,{"AK_ENABLE_COMBINED_CLUSTER":"1",
                                         "AK_ENABLE_PHONE_CMDS":"0",
                                         "AK_STEP128_ALLOW_TEST_PACKAGE":"1"},clear=True):
            with self.assertRaisesRegex(ValueError,"AK_ENABLE_PHONE_CMDS"):
                preflight.verify_requested_flags()
        with mock.patch.dict(os.environ,e|{"AK_STEP100_ALLOW_UNVERIFIED_PACKAGE":"1"},clear=True):
            with self.assertRaisesRegex(ValueError,"legacy package"):
                preflight.verify_requested_flags()

    def test_recovery_archive_never_extracted_or_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"safe.tar"
            expected=make_tar(path)
            before=path.read_bytes()
            members=preflight.audit_recovery_archive(path,expected_sha=expected)
            for name in preflight.REQUIRED_MEMBERS:
                self.assertEqual(members[name],
                                 hashlib.sha256(b"stock-"+name.encode()).hexdigest())
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(sorted(x.name for x in Path(temp).iterdir()),["safe.tar"])

    def test_wrong_archive_hash_and_missing_members_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"fake.tar"
            expected=make_tar(path)
            with self.assertRaisesRegex(ValueError,"SHA256"):
                preflight.audit_recovery_archive(path,expected_sha="0"*64)
            missing={n:b"x" for n in preflight.REQUIRED_MEMBERS if n!="sdDongle"}
            digest=make_tar(path,content=missing)
            with self.assertRaisesRegex(ValueError,"sdDongle"):
                preflight.audit_recovery_archive(path,expected_sha=digest)

    def test_archive_traversal_and_links_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"fake.tar"
            digest=make_tar(path,extra="../run_me")
            with self.assertRaisesRegex(ValueError,"unsafe archive"):
                preflight.audit_recovery_archive(path,digest)
            digest=make_tar(path,link="../../etc/passwd")
            with self.assertRaisesRegex(ValueError,"unsafe archive"):
                preflight.audit_recovery_archive(path,digest)

    def test_corrupt_or_different_stock_refused_without_builder(self):
        class FakeBuilder:
            def va_to_file_off(self,*args,**kwargs):
                raise AssertionError("should never inspect guessed ELF")
        with self.assertRaisesRegex(ValueError,"ELF is not"):
            preflight.audit_stock_elf(b"not-an-ELF",FakeBuilder())
        elf=bytearray(64)
        elf[:6]=b"\x7fELF\x01\x01"
        import struct
        struct.pack_into("<H",elf,16,2)
        struct.pack_into("<H",elf,18,40)
        with self.assertRaisesRegex(ValueError,"SHA256 differs"):
            preflight.audit_stock_elf(bytes(elf),FakeBuilder())

    def test_no_mutating_or_remote_transport_calls_in_preflight(self):
        s=SCRIPT.read_text()
        for forbidden in ("patch_sddongle(", "builder.main(", "make_tar(",
                          "post_chunk(", "urllib.request", "requests.post(",
                          "submition.cgi", "reboot.cgi", "flash_ak.py --",
                          "docker cp ", "docker exec ", "chmod(", ".write_bytes("):
            self.assertNotIn(forbidden,s)
        self.assertIn("work = bytearray(blob)",s)
        self.assertIn("work[off:off+size]=b",s)
        self.assertNotIn("blob[off:off+size]=",s)
        self.assertIn("return 2",s)

    def test_missing_local_stock_fails_without_filesystem_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with (mock.patch.object(preflight,"ROOT",root),
                  mock.patch.object(preflight,"source_git_status",return_value="fake"),
                  mock.patch.object(preflight,"verify_requested_flags",return_value=object())):
                self.assertEqual(preflight.run(),2)
            self.assertEqual(list(root.iterdir()),[])

if __name__=="__main__":
    unittest.main(verbosity=2)
