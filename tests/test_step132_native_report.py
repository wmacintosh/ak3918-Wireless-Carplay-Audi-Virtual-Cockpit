#!/usr/bin/env python3
"""Pinned-stock disassembly regression: queue destructor is NOT a callback drain.

The checked-in report is user-supplied output from the SHA-256-gated read-only
Step 132 extraction, not a synthetic model. These tests record the contract
of that *specific* stock AK3918 sdDongle; not any other firmware revision.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/AK3918_step132_queue_cancellation.txt"
SOURCE = ROOT / "altscreen.c"

NATIVE = {
    "DISPATCH QUEUE DESTRUCTOR pending node handling": {
        0xA0250: "e5943030",  # queue->pending head
        0xA0254: "e3530000",  # cmp pending,0
        0xA0258: "0a00000d",  # skip diagnostic when empty
        0xA0290: "ebfffa77",  # nonempty diagnostic/report path
        0xA033C: "eaffff93",  # tail branch to object free
    },
    "DISPATCH SERIAL QUEUE POP unlock and callback": {
        0xA304C: "e5945030",
        0xA3080: "ebfdd518",  # unlock
        0xA308C: "e12fff33",  # BLX r3 per-node callback
        0xA3094: "ebfdd3e4",  # free work node
    },
    "DISPATCH CONCURRENT QUEUE DRAIN comparison": {
        0xA0668: "e12fff33",  # BLX r3 per-node callback
        0xA0670: "ebfdde6d",  # free work node
    },
    "HTTP MESSAGE COMPLETE callback then message release": {
        0xA4C34: "e5913904",  # message->completion +0x904
        0xA4C4C: "e12fff33",  # BLX r3 completion callback
        0xA4C58: "eaff7806",  # tail CFRelease
    },
    "HTTP CLIENT ERROR HANDLER pending message drain": {
        0xA4EAC: "e594149c",  # client message list
        0xA4EC0: "ebffff54",  # HTTPClientCompleteMessage
        0xA4EC4: "eafffff8",  # loop until list empty
    },
    "HTTP CLIENT INVALIDATE enqueues callback": {
        0xA658C: "ebff71b8",  # CFRetain(client)
        0xA65A4: "eaffecd5",  # dispatch_async_f
    },
    "CAR GLOBAL CLIENT INVALIDATION": {
        0x2A78C: "eb01ef7c",  # invalidate client
        0x2A794: "eb016137",  # CFRelease
        0x2A79C: "e5843000",  # clear global
    },
}
HEADER = re.compile(r"^===== (.+?) =====\s*$", re.M)
OPCODE = re.compile(r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+(.+)$", re.I | re.M)


def read_sections(text):
    positions = list(HEADER.finditer(text))
    return {
        match.group(1): text[match.end(): positions[i + 1].start()
                               if i + 1 < len(positions) else len(text)]
        for i, match in enumerate(positions)
    }


class StockQueueSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = read_sections(EVIDENCE.read_text())

    def test_exact_arm_instructions_in_each_report_section(self):
        for section, expected in NATIVE.items():
            self.assertIn(section, self.sections)
            found = {
                int(addr, 16): encoding.lower()
                for addr, encoding, _ in OPCODE.findall(self.sections[section])
            }
            for addr, encoding in expected.items():
                with self.subTest(section=section, address=hex(addr)):
                    self.assertEqual(found.get(addr), encoding)

    def test_destructor_does_not_invoke_queued_nodes(self):
        destructor = self.sections["DISPATCH QUEUE DESTRUCTOR pending node handling"]
        # This is specifically the destructor function, not the dispatch
        # worker where indirect invocation is expected and verified above.
        self.assertNotRegex(destructor, r"\bblx\b")
        self.assertNotIn("bl\ta4c18", destructor)
        self.assertNotIn("free@plt", destructor)
        self.assertIn("a0250:", destructor)
        self.assertIn("a0290:", destructor)

    def test_current_source_preserves_accepted_request_tombstones(self):
        source = SOURCE.read_text()
        cancel = source.split("static void combo_cancel_all_requests_locked(void) {", 1)[1]
        cancel = cancel.split("static int combo_claim_request_locked", 1)[0]
        self.assertIn("g_combo_request[i].canceled = 1;", cancel)
        self.assertNotIn("memset(", cancel)
        self.assertIn("return 0; /* Fail closed if callbacks never arrive", source)
        self.assertIn("combo_consume_response_locked(msg, &gen, &connid);", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
