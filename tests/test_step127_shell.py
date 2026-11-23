#!/usr/bin/env python3
"""Regression tests for read-only Step 127 native queue audit."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/step127_extract_queue_completion.sh"


class Step127AuditTests(unittest.TestCase):
    def test_target_callback_pointer_math(self):
        # At a6a58: load signed PC-relative word fffff5d8.
        # At a6a60: add the resulting word to PC = a6a60 + 8.
        displacement = (0xfffff5d8 ^ 0x80000000) - 0x80000000
        self.assertEqual(displacement, -0xa28)
        self.assertEqual(0xa6a60 + 8 + displacement, 0xa6040)

    def test_shell_readonly_and_expected_ranges(self):
        source = SCRIPT.read_text()
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        self.assertIn("AK3918_step127_queue_completion.txt", source)
        self.assertIn("-v \"$ROOT:/repo:ro\"", source)
        self.assertIn("-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro", source)
        self.assertNotIn("build_hook.py", source)
        self.assertNotIn("AK_STEP100_ALLOW_UNVERIFIED_PACKAGE", source)
        match = re.search(r"<<'AK3918_READONLY'\n(.*?)\nAK3918_READONLY\n", source, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)
        subprocess.run(["bash", "-n", "-s"], input=body, text=True, check=True)
        self.assertIn('dump "HTTP QUEUED COMPLETION CALLBACK AND NEIGHBOURS" 0xa5e80 0xa6320', body)
        self.assertEqual(body.count('dump "'), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
