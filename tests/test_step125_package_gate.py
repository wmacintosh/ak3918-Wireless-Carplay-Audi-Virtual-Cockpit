#!/usr/bin/env python3
"""Ensure the historical package flag cannot create a combined-mode archive."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CombinedPackageGate(unittest.TestCase):
    def test_explicit_packaging_flag_refused_before_any_build(self):
        env = os.environ.copy()
        env['AK_ENABLE_COMBINED_CLUSTER'] = '1'
        env['AK_STEP100_ALLOW_UNVERIFIED_PACKAGE'] = '1'
        env.pop('AK_UCLIBC_CC', None)
        result = subprocess.run(
            [sys.executable, str(ROOT / 'build_hook.py')],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('REFUSING combined stream-111 firmware packaging',
                      result.stderr + result.stdout)
        self.assertIn('Only the separate, explicitly',
                      result.stderr + result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
