#!/usr/bin/env python3
"""Step 134 read-only client finalizer and global shutdown extraction safeguards.

These tests validate the extraction contract. They do NOT assert that normal
queue teardown drains all work or that it is safe to erase callback tombstones.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/step134_extract_client_finalizer.sh"
EVIDENCE = ROOT / "evidence/AK3918_step133_queue_ownership.txt"
SOURCE = ROOT / "altscreen.c"
EXPECTED_HASH = "b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1"
CRITICAL = [
    0x84660, 0xA63D8, 0xA641C, 0xA64A4, 0xA64A8,
    0xA6584, 0xA4F30, 0xA6040, 0xA32B0, 0xA33B4, 0xA342C,
    0xA0454, 0xA04BC, 0xA1900, 0xA1980, 0xA308C, 0xA30A4,
    0x2A78C, 0xA4D7C,
]
KNOWN_OPCODES = {
    0xA64A4: "e5840008",
    0xA64A8: "ebffe7e9",
    0xA342C: "eafff361",
    0xA30A4: "ebfff504",
}


class Step134QueueOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text()
        cls.native = EVIDENCE.read_text()
        cls.source = SOURCE.read_text()
        cls.embedded = re.search(
            r"<<'CHECK_REPORT'\n(.*?)\nCHECK_REPORT", cls.script, re.S
        )
        cls.disassembly = re.search(
            r"<<'ARM_READ_ONLY'\n(.*?)\nARM_READ_ONLY", cls.script, re.S
        )

    def test_local_extractor_syntax_and_no_write_paths(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        self.assertIn(EXPECTED_HASH, self.script)
        self.assertIn('-v "$ROOT:/repo:ro"', self.script)
        self.assertIn(
            '-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro',
            self.script,
        )
        self.assertIn('TEMP_REPORT="$(mktemp', self.script)
        self.assertIn('mv "$TEMP_REPORT" "$REPORT"', self.script)
        self.assertIn('trap \'rm -f "$TEMP_REPORT"\' EXIT', self.script)
        self.assertIn('REPORT="${1:-$HOME/Desktop/AK3918_step134_client_finalizer.txt}"', self.script)
        self.assertIn("HTTP MODULE CALLS INTO QUEUE REF AND ENQUEUE HELPERS", self.script)
        for unsafe in ("build_hook.py", "AK_STEP128_ALLOW_TEST_PACKAGE",
                       "flash_ak.py", "docker cp ", "docker exec ",
                       "AK_STEP100_ALLOW_UNVERIFIED_PACKAGE"):
            self.assertNotIn(unsafe, self.script)

    def test_disassembly_ranges_and_shell_heredoc(self):
        self.assertIsNotNone(self.disassembly)
        inner = self.disassembly.group(1)
        subprocess.run(["bash", "-n", "-s"], input=inner, text=True, check=True)
        self.assertEqual(inner.count('dump "'), 13)
        for name in ("CF RUNTIME CREATE AND REGISTER CONTEXT",
                     "HTTP CLASS REGISTER AND QUEUE OWNER SETUP",
                     "HTTP EARLY FINALIZER CANDIDATES",
                     "HTTP STATE MACHINE AND RELATED FINALIZERS",
                     "GLOBAL QUEUE ACCESS AND RETIREMENT",
                     "DISPATCH OBJECT RETAIN AND RELEASE",
                     "CAR-SIDE GLOBAL CLIENT INVALIDATE RELEASE"):
            self.assertIn(name, inner)

    def test_embedded_parser_compiles_and_rejects_bad_evidence(self):
        self.assertIsNotNone(self.embedded)
        parser = self.embedded.group(1)
        compile(parser, "Step134 embedded verifier", "exec")
        # Artificial fixture tests the fail-closed parser, not the native ELF.
        fixture = "\n".join(
            ["===== Section %02d =====" % i for i in range(14)]
            + [f"  {address:07x}:\t{KNOWN_OPCODES.get(address, 'e1a00000')} \tmock"
               for address in CRITICAL]
        )
        with tempfile.TemporaryDirectory(prefix="ak-step134-test-") as tmp:
            path = Path(tmp) / "fixture.txt"
            path.write_text(fixture)
            def run():
                return subprocess.run(
                    [sys.executable, "-", str(path)],
                    input=parser, text=True, capture_output=True, timeout=10
                )
            self.assertEqual(run().returncode, 0, "positive fixture rejected")
            path.write_text(fixture.replace(
                "a64a4:\te5840008", "a64a4:\te3a00001"))
            result = run()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unexpected native ARM opcode", result.stderr)
            path.write_text(fixture.replace(
                "a342c:\teafff361", "removed:\teafff361"))
            result = run()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing critical stock addresses", result.stderr)

    def test_existing_stock_queue_callback_constraints_unchanged(self):
        required_report = (
            "a0250:", "a0290:", "a308c:", "a3094:", "a4c4c:",
            "a4c58:", "a4ec0:", "a65a4:",
        )
        for item in required_report:
            self.assertIn(item, self.native)
        cancel = self.source.split(
            "static void combo_cancel_all_requests_locked(void) {", 1
        )[1].split("static int combo_claim_request_locked", 1)[0]
        self.assertIn("g_combo_request[i].canceled = 1;", cancel)
        self.assertNotIn("memset(", cancel)
        self.assertIn("return 0; /* Fail closed if callbacks never arrive", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
