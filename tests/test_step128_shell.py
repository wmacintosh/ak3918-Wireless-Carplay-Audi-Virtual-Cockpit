#!/usr/bin/env python3
"""Step 128 read-only stock HTTP processor extraction regression checks."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/step128_extract_http_processor.sh"


class Step128AuditTests(unittest.TestCase):
    def test_source_is_read_only_and_targets_processor(self):
        source = SCRIPT.read_text()
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        self.assertIn("AK3918_step128_http_processor.txt", source)
        self.assertIn('-v "$ROOT:/repo:ro"', source)
        self.assertIn('-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro', source)
        self.assertIn('sha256sum "$STOCK"', source)
        self.assertNotIn('build_hook.py', source)
        self.assertNotIn('AK_STEP100_ALLOW_UNVERIFIED_PACKAGE', source)
        match = re.search(r"<<'AK3918_READONLY'\n(.*?)\nAK3918_READONLY\n", source, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)
        subprocess.run(["bash", "-n", "-s"], input=body, text=True, check=True)
        self.assertIn('dump "HTTP CLIENT PROCESSOR ENTRY" 0xa52c0 0xa56c0', body)
        self.assertIn('dump "QUEUED CALLBACK AND CLIENT RELEASE" 0xa6040 0xa6074', body)
        self.assertEqual(body.count('dump "'), 6)
        for addr in ["a53fc", "a6040", "a6070", "a6a54", "2ee74"]:
            self.assertIn("0*" + addr + ":", source)

if __name__ == "__main__":
    unittest.main(verbosity=2)
