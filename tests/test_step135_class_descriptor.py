#!/usr/bin/env python3
"""Step 135 verified-stock CF descriptor candidate, read-only ELF32 decoder.

The native report has not yet been provided. Static candidate arithmetic is
proven from the pinned Step 133 opcode report; function identity is not.
"""
import importlib.util
from pathlib import Path
import re
import struct
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts/step135_extract_cf_class_descriptor.sh"
DECODER = ROOT / "scripts/step135_decode_cf_descriptor.py"
STOCK_REPORT = ROOT / "evidence/AK3918_step133_queue_ownership.txt"
SOURCE = ROOT / "altscreen.c"

spec = importlib.util.spec_from_file_location("ak_elf32", DECODER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class StockClassCandidate(unittest.TestCase):
    def test_exact_stock_pc_relative_callback_registration(self):
        report = STOCK_REPORT.read_text()
        ops = {int(a, 16): enc.lower() for a, enc in re.findall(
            r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+",
            report, re.I | re.M
        )}
        self.assertEqual(ops.get(0xA6368), "e59f0054")
        self.assertEqual(ops.get(0xA636C), "e08f0000")
        self.assertEqual(ops.get(0xA6370), "ebff78ba")
        self.assertEqual(ops.get(0xA63C4), "0008eb18")
        self.assertEqual(0xA636C + 8 + int(ops[0xA63C4], 16), 0x134E8C)
        self.assertEqual(ops.get(0xA64A8), "ebffe7e9")

    def test_shell_readonly_and_registration_guards(self):
        subprocess.run(["bash", "-n", str(AUDIT)], check=True)
        txt = AUDIT.read_text()
        self.assertIn("b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1", txt)
        self.assertIn('-v "$ROOT:/repo:ro"', txt)
        self.assertIn("-v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro", txt)
        self.assertIn('trap \'rm -f "$TEMP_REPORT"\' EXIT', txt)
        self.assertIn('mv "$TEMP_REPORT" "$REPORT"', txt)
        self.assertIn("0x134e8c", txt)
        self.assertIn("step135_decode_cf_descriptor.py", txt)
        self.assertIn('EXPECTED', txt)
        for disallowed in ("build_hook.py", "flash_ak.py", "docker exec ",
                           "docker cp ", "AK_STEP128_ALLOW_TEST_PACKAGE"):
            self.assertNotIn(disallowed, txt)

    @staticmethod
    def synthetic_arm_elf32(*, filebacked=True):
        # Test pure ELF mapping with a synthetic LOAD segment; does not claim
        # anything about actual stock class bytes or ABI.
        b = bytearray(0x200)
        ident = b"\x7fELF" + bytes([1, 1, 1]) + bytes(9)
        hdr = struct.pack("<16sHHIIIIIHHHHHH",
                          ident, 2, 40, 1, 0, 52, 0, 0, 52, 32, 1, 0, 0, 0)
        b[:len(hdr)] = hdr
        ph = struct.pack("<IIIIIIII", 1, 0x100, 0x134E80, 0,
                         0x80 if filebacked else 0x10,
                         0x100, 4, 0x1000)
        b[52:52+len(ph)] = ph
        b[0x10c:0x110] = struct.pack("<I", 0x12345678)
        b[0x11c:0x120] = struct.pack("<I", 0xA4F30)
        return b

    def test_elf32_program_headers_translate_vma(self):
        blob = self.synthetic_arm_elf32()
        chunk, details = module.read_image(blob, 0x134E8C, 0x40)
        self.assertEqual(chunk[:4], struct.pack("<I", 0x12345678))
        self.assertIn("LOAD[0]", details)
        rendered = module.format_descriptor(blob, 0x134E8C, 0x40)
        self.assertIn("0x12345678", rendered)
        self.assertIn("UNRELOCATED", rendered)
        self.assertIn("candidate", rendered)

    def test_bss_or_bad_elf_fails_closed(self):
        blob = self.synthetic_arm_elf32(filebacked=False)
        chunk, reason = module.read_image(blob, 0x134E8C, 0x40)
        self.assertIsNone(chunk)
        self.assertIn("not file-backed", reason)
        txt = module.format_descriptor(blob, 0x134E8C, 0x40)
        self.assertIn("UNAVAILABLE", txt)
        with self.assertRaisesRegex(ValueError, "ARM"):
            wrong = bytearray(self.synthetic_arm_elf32())
            wrong[18:20] = struct.pack("<H", 3)
            module.read_image(wrong, 0x134E8C, 0x40)
        with self.assertRaisesRegex(ValueError, "truncated program headers"):
            module.read_image(self.synthetic_arm_elf32()[:70], 0x134E8C, 0x40)
        with self.assertRaisesRegex(ValueError, "ELF32"):
            module.read_image(b"not an ELF".ljust(52, b"\0"), 0x134E8C, 0x40)

    def test_callback_tracking_remains_fail_closed(self):
        source = SOURCE.read_text()
        cancel = source.split("static void combo_cancel_all_requests_locked(void) {",1)[1].split(
            "static int combo_claim_request_locked(",1)[0]
        self.assertIn("g_combo_request[i].canceled = 1;",cancel)
        self.assertNotIn("memset(",cancel)
        self.assertIn("return 0; /* Fail closed if callbacks never arrive",source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
