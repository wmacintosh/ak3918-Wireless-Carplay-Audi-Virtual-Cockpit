#!/usr/bin/env python3
"""Step 139: stock SETUP request's zero-result wait is a baseline path.

The test pins a normalized excerpt from user-supplied ARM disassembly of
stock sdDongle. The model is intentionally small and NOT an emulator of
a15b8. It never runs target code or changes runtime firmware.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXCERPT = ROOT / "evidence/AK3918_step139_stock_send_wait_excerpt.txt"
DISPATCH = ROOT / "evidence/AK3918_step133_queue_ownership.txt"
SRC = ROOT / "altscreen.c"

EXPECTED = {
    0x2FBB0: "eb01db6f",  # call HTTPClientSendMessage 0xa6974
    0x2FBB8: "e1a04000",  # r4 <- native HTTP send status
    0x2FBF0: "e3540000",  # compare status with zero
    0x2FBF4: "0a000009",  # beq: success -> 0x2fc20
    0x2FC1C: "ea00006e",  # nonzero path exits to 0x2fddc
    0x2FC48: "e3e03000",  # r3 = -1
    0x2FC4C: "e3e02000",  # r2 = -1 (64-bit timeout all ones)
    0x2FC50: "e5960030",  # r0 = [context + 0x30]
    0x2FC54: "eb01c657",  # call semaphore wait candidate at 0xa15b8
    0x2EE68: "e59638fc",  # callback loads msg+0x8fc
    0x2EE70: "e5930030",  # loads same context's +0x30
    0x2EE74: "eb01c92f",  # invokes condition/semaphore signal helper a1338
}
STOCK_DISPATCH = {
    0xA1980: "ebfddc07",  # calloc
    0xA1988: "1a00000f",  # allocation success to node creation
    0xA19C8: "e8bd81f0",  # failed allocation -> return
    0xA19F4: "e5835000",  # insertion only after success branch
    0xA6A6C: "ebffeba3",  # void queue submission
    0xA6A70: "e3a05000",  # HTTP status zero after attempt
}


def instructions(text):
    return {int(addr, 16): value.lower()
            for addr, value in re.findall(
                r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+",
                text, re.I | re.M)}


@dataclass
class StockWaitModel:
    """Small counterfactual, not an implementation of dispatch_semaphore_wait."""
    http_result: int
    worker_published: bool
    semaphore_signalled: bool = False

    def enters_wait(self):
        return self.http_result == 0

    def is_blocked(self):
        return self.enters_wait() and not self.semaphore_signalled

    def callback(self):
        if not self.worker_published:
            raise AssertionError("modeled dropped work cannot execute its callback")
        self.semaphore_signalled = True


class StockBaselineWait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = EXCERPT.read_text()
        cls.arm = instructions(cls.raw)

    def test_user_stock_excerpt_pinned_opcodes(self):
        self.assertIn("user-supplied prior disassembly", self.raw)
        for address, value in EXPECTED.items():
            with self.subTest(address=f"{address:#x}"):
                self.assertEqual(self.arm.get(address), value)

    def test_exact_stock_dispatch_drop_and_forced_zero(self):
        stock = instructions(DISPATCH.read_text())
        for address, value in STOCK_DISPATCH.items():
            with self.subTest(address=f"{address:#x}"):
                self.assertEqual(stock.get(address), value)

    def test_normal_zero_result_reaches_all_ones_timeout_wait(self):
        data = self.raw
        self.assertLess(data.index("2fbb0:"), data.index("2fbf4:"))
        self.assertLess(data.index("2fbf4:"), data.index("2fc20:"))
        self.assertLess(data.index("2fc48:"), data.index("2fc4c:"))
        self.assertLess(data.index("2fc4c:"), data.index("2fc50:"))
        self.assertLess(data.index("2fc50:"), data.index("2fc54:"))
        self.assertIn("beq\t2fc20", data)
        self.assertIn("bl\ta15b8", data)
        self.assertIn("bl\ta1338", data)

    def test_oom_drop_can_block_stock_caller_without_callback(self):
        stock = StockWaitModel(http_result=0, worker_published=False)
        self.assertTrue(stock.enters_wait())
        self.assertTrue(stock.is_blocked())
        # No callback can be emitted by the dropped work node in this model,
        # so no response signal is produced. This is not a hardware hang test.
        self.assertFalse(stock.semaphore_signalled)

    def test_successful_worker_eventually_notifies_its_waiter(self):
        stock = StockWaitModel(http_result=0, worker_published=True)
        self.assertTrue(stock.is_blocked())
        stock.callback()
        self.assertFalse(stock.is_blocked())

    def test_nonzero_http_preparation_error_bypasses_wait(self):
        stock = StockWaitModel(http_result=-1, worker_published=False)
        self.assertFalse(stock.enters_wait())
        self.assertFalse(stock.is_blocked())

    def test_existing_tombstone_policy_is_unchanged(self):
        src = SRC.read_text()
        self.assertIn("#define COMBINED_REQUEST_LIMIT   8", src)
        self.assertIn("if (rc != 0)", src)
        self.assertIn("combo_forget_never_submitted_locked(ticket)", src)
        self.assertIn("g_combo_request[i].canceled = 1;", src)
        self.assertIn("return 0; /* Fail closed if callbacks never arrive", src)
        cancel = src.split("static void combo_cancel_all_requests_locked(void) {", 1)[1]
        cancel = cancel.split("static int combo_claim_request_locked", 1)[0]
        self.assertNotIn("memset(", cancel)

if __name__ == "__main__":
    unittest.main(verbosity=2)
