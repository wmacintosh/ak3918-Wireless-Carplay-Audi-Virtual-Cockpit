#!/usr/bin/env python3
"""Step 136 pinned stock class descriptor and finalizer-extraction safety gate."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/"evidence/AK3918_step135_cf_class_descriptor.txt"
SCRIPT = ROOT/"scripts/step136_extract_http_finalizer.sh"
SOURCE = ROOT/"altscreen.c"

def class_words(report):
    part=report.split("===== ELF32 CLIENT CLASS RECORD DECODE",1)[1]
    return {int(off,16): int(val,16) for off,val in
            re.findall(r"^\s*\+0x([0-9a-f]{2}): 0x([0-9a-f]{8})",part,re.M|re.I)}


class Step136CFClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence=EVIDENCE.read_text()
        cls.script=SCRIPT.read_text()

    def test_cfruntime_class_callback_candidate_from_verified_stock(self):
        e=self.evidence
        self.assertIn("000a6364",e)
        self.assertIn("a6370:\tebff78ba",e)
        self.assertIn("a63c4:\t0008eb18",e)
        self.assertIn("ELF32 ARM on-disk class-descriptor candidate at 0x00134e8c",e)
        self.assertIn(".data.rel.ro",e)
        self.assertIn("Elf file type is EXEC",e)
        w=class_words(e)
        self.assertEqual([w[i] for i in range(0,0x2c,4)],
                         [0,0x10abbe,0,0,0xa4b08,0,0,0,0,0,0])
        self.assertEqual(0xa636c+8+0x8eb18, 0x134e8c)
        self.assertEqual(w[0x30],0x10ad10)
        self.assertEqual(w[0x3c],0xa6cc0)

    def test_no_class_slot_relocation_shown_in_report(self):
        sec=self.evidence.split("===== RELOCATION ENTRIES NEAR CANDIDATE CLASS RECORD =====",1)[1].split("=====",1)[0]
        self.assertIn("Relocation section '.rel.dyn'",sec)
        self.assertNotRegex(sec,r"(?mi)^\s*00134e9c\s")
        self.assertNotRegex(sec,r"(?mi)^\s*00134e90\s")

    def test_extractor_shell_sha_mount_and_output_gates(self):
        subprocess.run(["bash","-n",str(SCRIPT)],check=True)
        s=self.script
        self.assertIn("b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1",s)
        self.assertIn('-v "$ROOT:/repo:ro"',s)
        self.assertIn("-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro",s)
        self.assertIn('REPORT="${1:-$HOME/Desktop/AK3918_step136_http_finalizer.txt}"',s)
        self.assertIn("0xa4b08",s)
        self.assertIn("0x0010abbe",s)
        self.assertIn('trap \'rm -f "$TEMP_REPORT"\' EXIT',s)
        self.assertIn('mv "$TEMP_REPORT" "$REPORT"',s)
        for forbidden in ("docker cp ","docker exec ","build_hook.py",
                          "AK_STEP128_ALLOW_TEST_PACKAGE","flash_ak.py",
                          "AK_STEP100_ALLOW_UNVERIFIED_PACKAGE"):
            self.assertNotIn(forbidden,s)

    def test_embedded_python_and_disassembly_sections(self):
        s=self.script
        for tag in ("VERIFY_CLASS_RECORD","VERIFY_DISASSEMBLY"):
            match=re.search(r"<<'"+tag+r"'\n(.*?)\n"+tag+r"\n",s,re.S)
            self.assertIsNotNone(match,tag)
            compile(match.group(1),tag,"exec")
        docker=re.search(r"<<'ARM_READ_ONLY'\n(.*?)\nARM_READ_ONLY",s,re.S)
        self.assertIsNotNone(docker)
        subprocess.run(["bash","-n","-s"],input=docker.group(1),
                       text=True,check=True)
        self.assertEqual(docker.group(1).count('dump "'),10)
        for q in ("HTTP CLIENT CLASS FINALIZER CANDIDATE AND NEIGHBORS",
                  "HTTP MESSAGE COMPLETION AND CALLBACK",
                  "GLOBAL DISPATCH QUEUE RETIREMENT",
                  "ELF RELOCATION TABLES","CLASS NAME STRING SOURCE"):
            self.assertIn(q,docker.group(1))
        self.assertIn('len(sections) != 13',s)

    def test_callback_tombstones_not_cleared_without_native_callback(self):
        src=SOURCE.read_text()
        cancel=src.split("static void combo_cancel_all_requests_locked(void) {",1)[1].split(
            "static int combo_claim_request_locked(",1)[0]
        self.assertIn("g_combo_request[i].canceled = 1;",cancel)
        self.assertNotIn("memset(",cancel)
        self.assertIn("return 0; /* Fail closed if callbacks never arrive",src)

if __name__=="__main__":
    unittest.main(verbosity=2)
