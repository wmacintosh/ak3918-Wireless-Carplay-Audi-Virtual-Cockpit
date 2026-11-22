#!/usr/bin/env python3
"""Step 137 native ARM result ambiguity and fail-closed ownership tests.

Pin the exact verified stock sdDongle paths. Static machine instruction
relationships are NOT proof of live-thread scheduling or callback delivery.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evidence/AK3918_step133_queue_ownership.txt"
FINALIZER = ROOT / "evidence/AK3918_step136_http_finalizer.txt"
SOURCE = ROOT / "altscreen.c"

HEADER = re.compile(r"^===== (.+?) =====$", re.M)
OP = re.compile(r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+", re.I | re.M)
ENQUEUE_OPS = {
    0xA1928: "0a00000e",  # invalid queue branch skips allocation
    0xA1968: "e5943004",  # load queue ref count
    0xA1970: "daffffed",  # invalid ref count skips allocation
    0xA1978: "e3a00001",  # calloc n=1
    0xA197C: "e3a0100c",  # size=12
    0xA1980: "ebfddc07",  # calloc
    0xA1984: "e2505000",  # test null
    0xA1988: "1a00000f",  # non-null goes to a19cc
    0xA19C0: "ebfff4ab",  # failure diagnostic
    0xA19C8: "e8bd81f0",  # return WITHOUT insertion
    0xA19CC: "e5857008",  # only non-null path begins node initialization
    0xA19EC: "ebfffa98",  # queue retain (when previously empty)
    0xA19F4: "e5835000",  # link node into queue
    0xA19FC: "e5845034",  # store tail
}
SEND_OPS = {
    0xA69C0: "e2505000",  # save prep error in r5
    0xA69C4: "0a00000e",  # prep success -> retain and dispatch
    0xA6A00: "ea00001b",  # prep failure -> return nonzero
    0xA6A4C: "ebff7088",  # retain message
    0xA6A54: "ebff7086",  # retain client
    0xA6A68: "e5960008",  # client+8 queue
    0xA6A6C: "ebffeba3",  # void dispatch_async_f
    0xA6A70: "e3a05000",  # force zero after dispatch attempt
    0xA6A74: "e1a00005",  # return r5
    0xA6A7C: "e8bd80f0",  # function returns
}

def sections(report):
    positions = list(HEADER.finditer(report))
    return {
        match.group(1): report[match.end(): positions[i+1].start() if i+1 < len(positions) else len(report)]
        for i, match in enumerate(positions)
    }

def assert_ops(chunk, expected):
    got = {int(addr, 16): encoding.lower() for addr, encoding in OP.findall(chunk)}
    for address, encoding in expected.items():
        if got.get(address) != encoding:
            raise ValueError(f"stock opcode mismatch at {address:#x}: {got.get(address)!r}, expected {encoding}")

class Step137NativeAmbiguity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = REPORT.read_text()
        cls.native = sections(cls.report)
        cls.source = SOURCE.read_text()

    def test_allocation_fail_path_does_not_link_work(self):
        chunk = self.native["ASYNC FUNCTION QUEUE NODE ENQUEUE"]
        assert_ops(chunk, ENQUEUE_OPS)
        self.assertLess(chunk.index("a1980:"), chunk.index("a1988:"))
        self.assertLess(chunk.index("a19c0:"), chunk.index("a19c8:"))
        self.assertLess(chunk.index("a19c8:"), chunk.index("a19cc:"))
        self.assertLess(chunk.index("a19cc:"), chunk.index("a19ec:"))
        self.assertLess(chunk.index("a19ec:"), chunk.index("a19f4:"))
        # a1988 branches to a19cc on success; failure falls through logging to
        # a19c8 return. No enqueue, no dispatch work-held queue retain.
        self.assertIn("bne\ta19cc", chunk)
        self.assertIn("pop\t{r4, r5, r6, r7, r8, pc}", chunk)

    def test_native_sender_returns_zero_regardless_of_dispatch_allocation(self):
        chunk = self.native["HTTP SEND USE OF CLIENT QUEUE"]
        assert_ops(chunk, SEND_OPS)
        self.assertLess(chunk.index("a6a4c:"), chunk.index("a6a6c:"))
        self.assertLess(chunk.index("a6a54:"), chunk.index("a6a6c:"))
        self.assertLess(chunk.index("a6a6c:"), chunk.index("a6a70:"))
        self.assertLess(chunk.index("a6a70:"), chunk.index("a6a74:"))
        self.assertIn("bl\ta1900", chunk)
        self.assertIn("mov\tr5, #0", chunk)
        self.assertIn("b\ta6a74", chunk)

    def test_native_drift_detected(self):
        enqueue = self.native["ASYNC FUNCTION QUEUE NODE ENQUEUE"]
        changed = enqueue.replace("a1988:\t1a00000f", "a1988:\te1a00000", 1)
        self.assertNotEqual(changed, enqueue)
        with self.assertRaisesRegex(ValueError, "opcode mismatch"):
            assert_ops(changed, ENQUEUE_OPS)
        send = self.native["HTTP SEND USE OF CLIENT QUEUE"]
        changed = send.replace("a6a70:\te3a05000", "a6a70:\te3a05001", 1)
        with self.assertRaisesRegex(ValueError, "opcode mismatch"):
            assert_ops(changed, SEND_OPS)

    def test_production_shim_never_guesses_queue_insertion_from_zero(self):
        c = self.source
        self.assertIn("#define COMBINED_REQUEST_LIMIT   8", c)
        f = c.split("static void combo_send_leave_locked(int rc, unsigned gen, uint64_t ticket)",1)[1]
        f = f.split("/* END STEP128 SEND ADMISSION GATE */",1)[0]
        self.assertIn("if (rc != 0)", f)
        self.assertIn("combo_forget_never_submitted_locked(ticket)", f)
        self.assertNotIn("if (rc == 0)", f)
        self.assertNotIn("time(", f)
        cancel = c.split("static void combo_cancel_all_requests_locked(void) {",1)[1]
        cancel = cancel.split("static int combo_claim_request_locked",1)[0]
        self.assertIn("g_combo_request[i].canceled = 1;", cancel)
        self.assertNotIn("memset(", cancel)
        consume = c.split("static void combo_consume_response_locked(void *msg,",1)[1]
        consume = consume.split("/* END STEP115 REQUEST HELPERS */",1)[0]
        self.assertIn("memset(r, 0, sizeof *r);", consume)
        self.assertIn("return 0; /* Fail closed if callbacks never arrive and slots fill. */", c)
        self.assertIn("int rc = http_send(client, msg)",c)

    def test_client_finalizer_is_not_a_missing_message_completion_barrier(self):
        f = sections(FINALIZER.read_text())["HTTP CLIENT CLASS FINALIZER CANDIDATE AND NEIGHBORS"]
        self.assertIn("a4b1c:\tebffee66", f)
        self.assertIn("a4b24:\te5843008", f)
        body = f[f.index("a4b08:"):f.index("a4bfc:")]
        self.assertNotIn("bl\ta4c18", body)
        self.assertNotIn("bl\ta1900", body)

if __name__ == "__main__":
    unittest.main(verbosity=2)
