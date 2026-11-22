#!/usr/bin/env python3
"""Pin the uploaded stock HTTPClient finalizer ARM control flow.

Only opcode and local ordering proofs for the SHA-256-gated stock sdDongle.
No assertion here promises callback delivery under OOM or process failure.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evidence/AK3918_step136_http_finalizer.txt"
SOURCE = ROOT / "altscreen.c"
HEAD = re.compile(r"^===== (.+?) =====$", re.M)
OP = re.compile(r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+", re.M | re.I)

CHECKS = {
    "HTTP CLIENT CLASS FINALIZER CANDIDATE AND NEIGHBORS": {
        0xA4B08: "e92d401f", # Finalizer entry
        0xA4B0C: "e1a04000", # Preserve client
        0xA4B10: "e5900008", # Load client+0x08 queue
        0xA4B14: "e3500000", # Check null
        0xA4B18: "0a000002", # Skip release on null
        0xA4B1C: "ebffee66", # dispatch_release(queue)
        0xA4B20: "e3a03000", # zero
        0xA4B24: "e5843008", # clear client+0x08
        0xA4B28: "e5940018", # load optional buffer client+0x18
        0xA4B34: "ebfdcd3c", # free buffer
        0xA4B3C: "e5843018", # clear buffer
        0xA4B40: "e594347c", # callback pointer client+0x47c
        0xA4B4C: "e5940474", # callback context client+0x474
        0xA4B50: "e12fff33", # invoke optional callback
        0xA4B94: "e5940044", # client socket fd
        0xA4BA0: "ebfdd0b1", # close
        0xA4BF0: "e5843044", # client socket fd=-1
    },
    "HTTP CLASS INIT AND QUEUE RETAIN": {
        0xA64A0: "ebfff382", # global queue
        0xA64A4: "e5840008", # store client+8
        0xA64A8: "ebffe7e9", # retain queue
    },
    "SERIAL DISPATCH LAST WORK RELEASE": {
        0xA308C: "e12fff33", # invoke queued callback
        0xA3094: "ebfdd3e4", # free work node
        0xA30A4: "ebfff504", # release queue's active-work ref
    },
    "HTTP CLIENT ERROR DRAIN AND RELEASE": {
        0xA4EC0: "ebffff54", # process pending message
        0xA4EC4: "eafffff8", # drain list
        0xA4F48: "eaff774a", # client CFRelease in invalidation callback
    },
    "HTTP MESSAGE COMPLETION AND CALLBACK": {
        0xA4C4C: "e12fff33",
        0xA4C58: "eaff7806",
    },
    "CAR SIDE HTTP CLIENT INVALIDATE RELEASE": {
        0x2A78C: "eb01ef7c", # queue invalidation
        0x2A794: "eb016137", # release global client
        0x2A79C: "e5843000", # clear global
    },
}


def split_sections(report):
    matches = list(HEAD.finditer(report))
    return {
        match.group(1): report[match.end():matches[i+1].start()
                               if i+1<len(matches) else len(report)]
        for i, match in enumerate(matches)
    }


def validate(report):
    sections = split_sections(report)
    if len(sections) != 13:
        raise ValueError("Step136 evidence must contain 13 sections")
    for name, expected in CHECKS.items():
        if name not in sections:
            raise ValueError("Missing native section: " + name)
        found = {int(a,16): w.lower() for a,w in OP.findall(sections[name])}
        for addr, opcode in expected.items():
            if found.get(addr) != opcode:
                raise ValueError(
                    f"{name}: stock opcode mismatch at {addr:#x}, "
                    f"{found.get(addr)!r} != {opcode}"
                )
    return sections


class NativeFinalizerOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REPORT.read_text()
        cls.sections = validate(cls.text)

    def test_exact_stock_finalizer_opcodes(self):
        validate(self.text)

    def test_mutation_detects_changed_queue_release(self):
        self.assertIn("a4b1c:\tebffee66", self.text)
        bad = self.text.replace("a4b1c:\tebffee66", "a4b1c:\te1a00000", 1)
        with self.assertRaisesRegex(ValueError, "opcode mismatch"):
            validate(bad)

    def test_client_queue_release_is_first_in_finalizer(self):
        code = self.sections["HTTP CLIENT CLASS FINALIZER CANDIDATE AND NEIGHBORS"]
        self.assertLess(code.index("a4b10:"), code.index("a4b1c:"))
        self.assertLess(code.index("a4b1c:"), code.index("a4b24:"))
        self.assertLess(code.index("a4b24:"), code.index("a4b34:"))
        self.assertLess(code.index("a4b34:"), code.index("a4b50:"))
        self.assertLess(code.index("a4b50:"), code.index("a4ba0:"))
        finalizer = code[code.index("a4b08:"):code.index("a4bfc:")]
        self.assertEqual(finalizer.count("bl\ta04bc"), 1)
        self.assertNotIn("bl\ta4c18", finalizer)  # No HTTP pending-list drain
        self.assertIn("blx\tr3", finalizer)       # Optional non-HTTP callback

    def test_queue_work_release_after_dispatch_callback(self):
        code = self.sections["SERIAL DISPATCH LAST WORK RELEASE"]
        self.assertLess(code.index("a308c:"), code.index("a30a4:"))
        code = self.sections["HTTP CLIENT ERROR DRAIN AND RELEASE"]
        self.assertLess(code.index("a4ec0:"), code.index("a4f48:"))

    def test_tombstones_remain_fail_closed(self):
        src = SOURCE.read_text()
        cancel = src.split("static void combo_cancel_all_requests_locked(void) {",1)[1]
        cancel = cancel.split("static int combo_claim_request_locked",1)[0]
        self.assertIn("g_combo_request[i].canceled = 1;", cancel)
        self.assertNotIn("memset(", cancel)
        self.assertIn("return 0; /* Fail closed if callbacks never arrive", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
