#!/usr/bin/env python3
"""Fail-closed package policy independent of cross-compiler availability."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ak3918_build_policy", ROOT / "build_hook.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class PackagePolicy(unittest.TestCase):
    def plan(self, combined, legacy=False, test_only=False):
        with patch.object(build, "ENABLE_COMBINED_CLUSTER", combined):
            with patch.dict(os.environ, {
                "AK_STEP100_ALLOW_UNVERIFIED_PACKAGE": "1" if legacy else "0",
                "AK_STEP128_ALLOW_TEST_PACKAGE": "1" if test_only else "0",
            }):
                return build.package_plan()

    def test_default_never_generates_archive(self):
        self.assertIsNone(self.plan(False))
        self.assertIsNone(self.plan(True))

    def test_legacy_archive_only_without_combined(self):
        self.assertEqual(self.plan(False, legacy=True), "ak_hook.tar")
        for both in (False, True):
            with self.subTest(test_flag=both):
                with self.assertRaisesRegex(SystemExit, "REFUSING combined"):
                    self.plan(True, legacy=True, test_only=both)

    def test_experimental_archive_never_uses_legacy_filename(self):
        self.assertEqual(self.plan(True, test_only=True),
                         "ak_hook_step128_test.tar")
        with self.assertRaisesRegex(SystemExit, "REFUSING AK_STEP128"):
            self.plan(False, test_only=True)

    def test_invalid_flags_abort_before_creating_output(self):
        # Missing compiler would fail much later; the policy must fail first.
        env = os.environ.copy()
        env.update(AK_ENABLE_COMBINED_CLUSTER="1",
                   AK_STEP100_ALLOW_UNVERIFIED_PACKAGE="1",
                   AK_STEP128_ALLOW_TEST_PACKAGE="1")
        env.pop("AK_UCLIBC_CC", None)
        result = subprocess.run(
            [sys.executable, str(ROOT / "build_hook.py")],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REFUSING combined stream-111", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
