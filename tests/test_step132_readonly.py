#!/usr/bin/env python3
"""Step 132 source-only audit script regression checks."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/step132_extract_queue_cancellation.sh"

class Step132ReadOnly(unittest.TestCase):
    def test_verified_stock_only_no_firmware_write(self):
        text=SCRIPT.read_text()
        subprocess.run(["bash","-n",str(SCRIPT)],check=True)
        self.assertIn("b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1",text)
        self.assertIn("-v \"$ROOT:/repo:ro\"",text)
        self.assertIn("-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro",text)
        self.assertIn('REPORT="${1:-$HOME/Desktop/AK3918_step132_queue_cancellation.txt}"',text)
        self.assertIn('mv "$TEMP_REPORT" "$REPORT"',text)
        self.assertNotIn("build_hook.py",text)
        self.assertNotIn("AK_STEP128_ALLOW_TEST_PACKAGE",text)
        self.assertNotIn("AK_STEP100_ALLOW_UNVERIFIED_PACKAGE",text)
        match=re.search(r"<<'ARM_READ_ONLY'\n(.*?)\nARM_READ_ONLY",text,re.S)
        self.assertIsNotNone(match)
        subprocess.run(["bash","-n","-s"],input=match.group(1),text=True,check=True)
        self.assertEqual(match.group(1).count('dump "'),9)
        for addr in ("0xa01b8","0xa304c","0xa058c","0xa4c18","0xa4d7c",
                     "0xa4f30","0xa6584","0xa6040"):
            self.assertIn(addr,match.group(1))
        self.assertIn("pending node handling",match.group(1))
    def test_source_does_not_reclaim_on_cancel_or_elapsed_time(self):
        src=(ROOT/"altscreen.c").read_text()
        block=src.split("static void combo_cancel_all_requests_locked(void) {",1)[1].split(
            "static int combo_claim_request_locked(",1)[0]
        self.assertIn("g_combo_request[i].canceled = 1;",block)
        self.assertNotIn("memset(r,",block)
        self.assertNotIn("cf_release(",block)
        self.assertNotIn("free(r)",block)
        self.assertNotIn("clock_gettime",block)

if __name__=="__main__":
    unittest.main(verbosity=2)
