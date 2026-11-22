#!/usr/bin/env python3
"""Step142 pure host tests for isolated ARM build and static ELF audit helpers."""
import importlib.util
from pathlib import Path
import re
import struct
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/"scripts/step142_audit_patched_elf.py"
SCRIPT=ROOT/"scripts/step142_isolated_elf_audit.sh"
spec=importlib.util.spec_from_file_location("step142_elfaudit",AUDIT)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditNegativeControls(unittest.TestCase):
    def test_arm_bl_decode_forward_backward_and_sign(self):
        self.assertEqual(audit.arm_bl_dest(0x2fadc,0xeb018de6),0x9327c)
        self.assertEqual(audit.arm_bl_dest(0x2fbb0,0xeb01db6f),0xa6974)
        self.assertEqual(audit.arm_bl_dest(0x5ec50,0xeb002e6d),0x6a60c)
        self.assertEqual(audit.arm_bl_dest(0x1000,0xebfffffe),0x1000)
        with self.assertRaisesRegex(ValueError,"unconditional BL"):
            audit.arm_bl_dest(0x1000,0xeafffffe)
        with self.assertRaisesRegex(ValueError,"unconditional BL"):
            audit.arm_bl_dest(0x1000,0xfa000000)

    def test_elf_headers_reject_non_arm_or_other_endianness(self):
        with self.assertRaisesRegex(ValueError,"not ELF32"):
            audit.elf_header(b"evil","test")
        b=bytearray(80)
        b[:6]=b"\x7fELF\x01\x01"
        struct.pack_into("<HH",b,16,2,40)
        struct.pack_into("<H",b,42,32)
        audit.elf_header(b,"ARM ELF32")
        b[5]=2
        with self.assertRaisesRegex(ValueError,"not ELF32"):
            audit.elf_header(b,"big-endian")
        b[5]=1
        struct.pack_into("<H",b,18,62)
        with self.assertRaisesRegex(ValueError,"not ARM"):
            audit.elf_header(b,"x86")

    def test_dyn_string_bounds(self):
        buf=b"Hello\x00$ORIGIN\x00padding"
        self.assertEqual(audit.dyn_string(buf,0,6,14),b"$ORIGIN")
        with self.assertRaisesRegex(ValueError,"outside STRSZ"):
            audit.dyn_string(buf,0,14,14)
        with self.assertRaisesRegex(ValueError,"unterminated"):
            audit.dyn_string(b"aaaa",0,0,4)

    def test_shell_has_correct_disposable_separation(self):
        s=SCRIPT.read_text()
        subprocess.run(["bash","-n",str(SCRIPT)],check=True)
        self.assertIn("--network none",s)
        self.assertIn("--pull never",s)
        self.assertIn('-v "$HERE:/repo:ro"',s)
        self.assertIn('-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro',s)
        self.assertIn('mktemp -d /tmp/ak3918-step142-disposable.',s)
        self.assertIn('trap \'rm -rf "$WORK"\' EXIT',s)
        self.assertIn('trap \'rm -rf "$TEMP"\' EXIT',s)
        self.assertIn("build_hook.build_shim",s)
        self.assertIn("build_hook.patch_sddongle",s)
        self.assertIn('repair("modified/sdDongle")',s)
        self.assertIn('AK_ENABLE_COMBINED_CLUSTER=1',s)
        self.assertIn('AK_ENABLE_PHONE_CMDS=1',s)
        self.assertIn('export AK_STEP128_ALLOW_TEST_PACKAGE=0',s)
        self.assertIn('export AK_STEP100_ALLOW_UNVERIFIED_PACKAGE=0',s)
        self.assertIn('if build_hook.package_plan() is not None:',s)
        self.assertIn("python3 /repo/scripts/step142_audit_patched_elf.py",s)
        self.assertIn('cp "$RESULT" "$REPORT"',s)
        for forbidden in ("make_tar(", "builder.main(", "build_hook.main(",
                          "flash_ak.py", "submition.cgi", "reboot.cgi",
                          "post_chunk(", "docker cp ", "--network host"):
            self.assertNotIn(forbidden,s)
        # The host repository is mounted read-only, compiled ELF never leaves
        # the ephemeral container; only terminal text is reported.
        self.assertNotRegex(s,r"\-v\s+[^\n]*:(?:/work|/tmp/ak3918-step142-disposable):rw")

    def test_auditor_enforces_full_combined_patch_contract(self):
        s=AUDIT.read_text()
        for tag in (
            "STOCK_SHA",
            "arm_bl_dest",
            "0x02FADC,0xEB018DE6,0x0013C644",
            "0x02FBB0,0xEB01DB6F,0x0013C648",
            "0x05EC50,0xEB002E6D,0x001369FC",
            "0x00134078","0x0013C640",
            "new_bss[2]==old_bss[2]+12",
            "DT_STRTAB/DT_STRSZ",
            "RUNPATH=$ORIGIN",
            "libc.so.0",
            "shim_screen_response",
            "BLOCKED FOR FLASH",
        ):
            self.assertIn(tag,s)
        for forbidden in ("patch_sddongle(", "repair_elf.repair(",
                          "make_tar(", "open(dst, ", ".write_bytes(",
                          "urllib.request", "requests.post(", "submition.cgi"):
            self.assertNotIn(forbidden,s)

    def test_no_synthetic_pass_for_invalid_original_stock(self):
        class FakeBuilder:
            pass
        with self.assertRaisesRegex(ValueError,"not ELF32"):
            audit.audit(Path("/nonexistent"),Path("/nonexistent"),
                        Path("/nonexistent"),FakeBuilder())


if __name__=="__main__":
    unittest.main(verbosity=2)
