#!/usr/bin/env python3
"""Validate read-only Step 126 extraction source and container heredoc syntax."""
from pathlib import Path
import re
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'step126_extract_ownership_and_dispatch.sh'


class Step126Script(unittest.TestCase):
    def test_shell_and_mounts(self):
        source = SCRIPT.read_text()
        subprocess.run(['bash', '-n', str(SCRIPT)], check=True)
        self.assertIn('AK3918_step126_ownership_and_dispatch.txt', source)
        self.assertIn('b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1', source)
        self.assertIn('-v "$ROOT:/repo:ro"', source)
        self.assertIn('-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro', source)
        self.assertNotIn('build_hook.py', source)
        self.assertNotIn('AK_STEP100_ALLOW_UNVERIFIED_PACKAGE', source)
        match = re.search(r"<<'AK3918_READONLY'\n(.*?)\nAK3918_READONLY\n", source, re.DOTALL)
        self.assertIsNotNone(match)
        subprocess.run(['bash', '-n', '-s'], input=match.group(1),
                       text=True, check=True)
        self.assertEqual(match.group(1).count('dump "'), 8)


if __name__ == '__main__':
    unittest.main(verbosity=2)
