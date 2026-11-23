#!/usr/bin/env python3
"""Step 133: pin uploaded stock ARM queue-lifetime evidence.

The checks prove only the machine-instruction relationships in the exact
SHA-256 verified stock sdDongle report. They do not guarantee eventual
callback delivery, especially on out-of-memory or process failure.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evidence/AK3918_step133_queue_ownership.txt"
SOURCE = ROOT / "altscreen.c"
HEADER = re.compile(r"^===== (.+?) =====\s*$", re.M)
INSTRUCTION = re.compile(
    r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+", re.I | re.M
)

# Native opcodes are taken from the user-supplied, verified-stock report.
EXPECTED = {
    "QUEUE SCHEDULING AND WAKE HELPERS": {
        0xA0454: "e250c000",  # dispatch retain with non-null check
        0xA0498: "e3a01001",  # increment by +1
        0xA04A0: "eb013efa",  # atomic modify
        0xA04BC: "e92d401f",  # dispatch release entry
        0xA0500: "e3e01000",  # decrement by -1
        0xA0508: "eb013ee0",  # atomic modify
        0xA0550: "e594300c",  # load zero-refcount finalizer
        0xA0560: "e12fff13",  # invoke finalizer
    },
    "ASYNC FUNCTION QUEUE NODE ENQUEUE": {
        0xA1968: "e5943004",  # queue refcount check
        0xA197C: "e3a0100c",  # request 12 byte work node
        0xA1980: "ebfddc07",  # calloc
        0xA1984: "e2505000",  # test allocation outcome
        0xA1988: "1a00000f",  # success goes to enqueue
        0xA19C0: "ebfff4ab",  # failure diagnostic
        0xA19C8: "e8bd81f0",  # failure returns without enqueue
        0xA19DC: "e5947030",  # prior work head
        0xA19E4: "1a000001",  # do not retain if already nonempty
        0xA19EC: "ebfffa98",  # retain queue when empty -> nonempty
        0xA19F4: "e5835000",  # append the new work node
        0xA19FC: "e5845034",  # update queue tail
    },
    "SERIAL QUEUE DISPATCH POP AND CALLBACK": {
        0xA3078: "03a06001",  # last node flag
        0xA308C: "e12fff33",  # work callback
        0xA3094: "ebfdd3e4",  # free work node
        0xA30A4: "ebfff504",  # release queue when drained
    },
    "QUEUE CREATOR AND ATTACHMENT HELPER": {
        0xA32B0: "e92d401f",  # process queue getter
        0xA32B4: "ebfffaec",  # dispatch initialization
        0xA32FC: "e5934024",  # globally stored queue pointer
        0xA333C: "e1a00004",  # return queue
    },
    "HTTP CLIENT INIT QUEUE ASSIGNMENT": {
        0xA64A0: "ebfff382",  # global queue getter
        0xA64A4: "e5840008",  # queue pointer stored client+8
        0xA64A8: "ebffe7e9",  # explicit queue retain
    },
    "HTTP SEND USE OF CLIENT QUEUE": {
        0xA6A4C: "ebff7088",  # retains message before queue
        0xA6A54: "ebff7086",  # retains client before queue
        0xA6A68: "e5960008",  # reads client+8
        0xA6A6C: "ebffeba3",  # void dispatch_async_f
        0xA6A70: "e3a05000",  # always returns success after attempt
    },
    "QUEUE OBJECT DESTRUCTOR NONEMPTY ASSERTION": {
        0xA0250: "e5943030",  # pending head
        0xA0258: "0a00000d",  # skip warning when empty
    },
}


def parse_sections(report):
    m = list(HEADER.finditer(report))
    return {
        h.group(1): report[h.end(): m[i+1].start() if i+1<len(m) else len(report)]
        for i, h in enumerate(m)
    }


def verify(report):
    sections = parse_sections(report)
    if len(sections) != 12:
        raise ValueError(f"Expected 12 stock disassembly sections, got {len(sections)}")
    for name, expected in EXPECTED.items():
        if name not in sections:
            raise ValueError(f"Missing section {name}")
        got = {
            int(addr, 16): opcode.lower()
            for addr, opcode in INSTRUCTION.findall(sections[name])
        }
        for addr, opcode in expected.items():
            if got.get(addr) != opcode:
                raise ValueError(
                    f"{name}: wrong or missing opcode at {addr:#x}: "
                    f"{got.get(addr)!r}, expected {opcode!r}"
                )
    # Source does not currently infer completion from elapsed time/teardown.
    src = SOURCE.read_text()
    cancel = src.split("static void combo_cancel_all_requests_locked(void) {", 1)[1]
    cancel = cancel.split("static int combo_claim_request_locked(", 1)[0]
    if "g_combo_request[i].canceled = 1;" not in cancel or "memset(" in cancel:
        raise ValueError("Accepted-request tombstone policy changed")
    if "return 0; /* Fail closed if callbacks never arrive" not in src:
        raise ValueError("Fail-closed capacity limit changed")


class NativeQueueOwnership(unittest.TestCase):
    def test_uploaded_stock_disassembly_consistent(self):
        verify(REPORT.read_text())

    def test_opcode_drift_is_detected(self):
        report = REPORT.read_text()
        self.assertIn("a19ec:\tebfffa98", report)
        mutated = report.replace(
            "a19ec:\tebfffa98", "a19ec:\te1a00000", 1
        )
        with self.assertRaisesRegex(ValueError, "wrong or missing opcode"):
            verify(mutated)

    def test_allocation_failure_is_not_silent_enqueue_success(self):
        sections = parse_sections(REPORT.read_text())
        enqueue = sections["ASYNC FUNCTION QUEUE NODE ENQUEUE"]
        addresses = {
            int(addr, 16) for addr, _ in INSTRUCTION.findall(enqueue)
        }
        self.assertLess(0xA1980, 0xA1988)
        self.assertLess(0xA1988, 0xA19C0)
        self.assertIn(0xA19C8, addresses)
        self.assertIn("a19cc:", enqueue)
        self.assertNotIn("a19cc:\t0a", enqueue)

    def test_callback_precedes_work_ref_release(self):
        sections = parse_sections(REPORT.read_text())
        drain = sections["SERIAL QUEUE DISPATCH POP AND CALLBACK"]
        self.assertLess(drain.index("a308c:"), drain.index("a30a4:"))
        enqueue = sections["ASYNC FUNCTION QUEUE NODE ENQUEUE"]
        self.assertLess(enqueue.index("a19ec:"), enqueue.index("a19f4:"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
