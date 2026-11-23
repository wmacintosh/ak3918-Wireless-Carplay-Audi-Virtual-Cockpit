#!/usr/bin/env python3
"""Step 131 stock-send proof must fail on changed opcodes or missing branches."""
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/step131_verify_http_return.py"
EXTRACT = ROOT / "scripts/step131_extract_http_return.sh"
spec = importlib.util.spec_from_file_location("ak3918_http131", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def stock_instruction_fixture():
    # Minimal complete expected instruction set, generated from the verified
    # opcode table itself; corruption tests exercise the actual gate.
    return "\n".join(
        f"  {addr:07x}:\t{opcode} \tstub"
        for addr, opcode in audit.EXPECTED.items()
    ) + "\n"


class NativeHTTPReturnProof(unittest.TestCase):
    def test_known_opcodes_pass(self):
        audit.verify(stock_instruction_fixture())

    def test_changed_early_exit_opcode_rejected(self):
        corrupt = stock_instruction_fixture().replace(
            "a6a00:\tea00001b", "a6a00:\te3a05000")
        with self.assertRaisesRegex(ValueError, "Unverified native"):
            audit.verify(corrupt)

    def test_missing_success_return_rejected(self):
        missing = "\n".join(
            line for line in stock_instruction_fixture().splitlines()
            if "a6a70:" not in line
        )
        with self.assertRaisesRegex(ValueError, "missing instruction"):
            audit.verify(missing)

    def test_unsafe_gate_missing_or_unreadable_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing instruction"):
            audit.verify("000a6974: e5913410 ldr r3")

    def test_extractor_reads_exact_stock_and_never_packages(self):
        script = EXTRACT.read_text()
        subprocess.run(["bash", "-n", str(EXTRACT)], check=True)
        self.assertIn("b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1",script)
        self.assertIn('-v "$ROOT:/repo:ro"', script)
        self.assertIn('-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro', script)
        self.assertIn("step131_verify_http_return.py", script)
        self.assertIn("0xa6974 --stop-address=0xa6a80", script)
        self.assertNotIn("build_hook.py", script)
        self.assertNotIn("AK_STEP128_ALLOW_TEST_PACKAGE", script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
