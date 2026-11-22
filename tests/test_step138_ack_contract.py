#!/usr/bin/env python3
"""Step 138: static-source-backed feasibility model for enqueue acknowledgments.

The stock ARM evidence establishes that an HTTP sender's return value does
not report whether dispatch_async_f allocated/linked its node.

This small state-machine study is MODEL TESTING ONLY: it neither patches nor
intercepts the native dispatcher and does not imply real device availability.
"""
from dataclasses import dataclass
from enum import Enum
from itertools import permutations
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "evidence/AK3918_step133_queue_ownership.txt"
FINALIZER = ROOT / "evidence/AK3918_step136_http_finalizer.txt"
SHIM = ROOT / "altscreen.c"
REQUIRED_ARM = {
    0xA1980: "ebfddc07",   # calloc(1,12)
    0xA1988: "1a00000f",   # successful allocation -> node initialization
    0xA19C8: "e8bd81f0",   # failed allocation exits without enqueue
    0xA19F4: "e5835000",   # link node to queue
    0xA6A4C: "ebff7088",   # retain native message
    0xA6A54: "ebff7086",   # retain native client
    0xA6A6C: "ebffeba3",   # dispatch_async_f
    0xA6A70: "e3a05000",   # return zero
    0xA3074: "e5843030",   # worker dequeues work from queue+0x30
    0xA308C: "e12fff33",   # worker executes dispatch callback
    0xA30A4: "ebfff504",   # worker releases queued-work reference
}


def pin_stock_native_control_flow():
    report = STOCK.read_text()
    opcodes = {
        int(address,16): word.lower()
        for address, word in re.findall(
            r"^\s*([0-9a-f]{5,8}):\s+([0-9a-f]{8})\s+",
            report, re.I | re.M
        )
    }
    for address, expected in REQUIRED_ARM.items():
        if opcodes.get(address) != expected:
            raise AssertionError(
                f"stock opcode missing or drifted at {address:#x}: "
                f"{opcodes.get(address)!r}, wanted {expected!r}"
            )
    finalizer = FINALIZER.read_text()
    assert "a4b1c:\tebffee66" in finalizer
    assert "a4b24:\te5843008" in finalizer
    c = SHIM.read_text()
    assert "#define COMBINED_REQUEST_LIMIT   8" in c
    assert "if (rc != 0)" in c
    assert "combo_forget_never_submitted_locked(ticket)" in c
    assert "g_combo_request[i].canceled = 1;" in c
    assert "return 0; /* Fail closed if callbacks never arrive" in c


@dataclass(frozen=True)
class SeenAtShim:
    """A coarse observation; not a real in-process queue instrumentation."""
    http_return: int
    pending_queue_nodes: int
    http_completion_seen: bool
    still_has_ticket: bool


class NativePath(Enum):
    DROPPED_BY_CALLOC = "calloc failed, no dispatch node"
    LINKED_BUT_NOT_YET_DISPATCHED = "work node published to queue"
    LINKED_WORKER_DEQUEUED = "worker dequeued; HTTP completion still pending"


def observable(path: NativePath) -> SeenAtShim:
    if path == NativePath.LINKED_BUT_NOT_YET_DISPATCHED:
        return SeenAtShim(0,1,False,True)
    # The worker can remove a successfully linked node very quickly.
    # Even a privileged read-only queue-depth snapshot sees zero on BOTH
    # a failed allocation and successfully dequeued work.
    return SeenAtShim(0,0,False,True)


class Ack(Enum):
    UNKNOWN = "no per-request native signal"
    DROPPED = "native was proved NOT to link a work node"
    PUBLISHED = "native was proved to link a work node"


@dataclass(frozen=True)
class NativeReceipt:
    """Proposed instrumentation contract, NOT exposed by the stock sender."""
    ticket: int
    ack: Ack
    native_retains_balanced: bool
    proves_no_future_work_callback: bool


def permitted_reclaim(receipt: NativeReceipt, callback_seen: bool) -> bool:
    """Strict proposed design gate; only the stock callback is accepted today."""
    if callback_seen:
        return True
    return (
        receipt.ack == Ack.DROPPED
        and receipt.native_retains_balanced
        and receipt.proves_no_future_work_callback
    )


class Tracking:
    """Candidate per-ticket receipts, with late acknowledgment races."""
    def __init__(self):
        self.state = "reserved"
        self.acks = 0
        self.deliveries = 0

    def mark_published(self):
        self.acks += 1
        if self.state == "reserved":
            self.state = "pending"
        # Never resurrect a completed ticket if ack follows callback.

    def on_http_completion(self):
        self.deliveries += 1
        self.state = "complete"

    def request_reclaim(self, receipt: NativeReceipt):
        if self.state == "complete":
            return
        if permitted_reclaim(receipt, callback_seen=False):
            self.state = "complete"


class AckFeasibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pin_stock_native_control_flow()

    def test_queue_length_snapshot_cannot_identify_failed_allocation(self):
        dropped = observable(NativePath.DROPPED_BY_CALLOC)
        dequeued = observable(NativePath.LINKED_WORKER_DEQUEUED)
        self.assertEqual(dropped, dequeued)
        self.assertEqual(dropped.http_return,0)
        self.assertFalse(dequeued.http_completion_seen)
        # A nonempty queue only shows some work exists, not this msg's ID.
        self.assertNotEqual(dropped,observable(NativePath.LINKED_BUT_NOT_YET_DISPATCHED))

    def test_expiry_and_reconnect_add_no_native_ack(self):
        for path in NativePath:
            observed = observable(path)
            self.assertTrue(observed.still_has_ticket)
            # No observation here proves the identity of queued work,
            # completion or impossibility of future callbacks.
            receipt = NativeReceipt(101,Ack.UNKNOWN,False,False)
            self.assertFalse(permitted_reclaim(receipt,False))

    def test_explicit_publish_ack_is_not_http_completion(self):
        pub = NativeReceipt(101,Ack.PUBLISHED,False,False)
        self.assertFalse(permitted_reclaim(pub,False))
        self.assertTrue(permitted_reclaim(pub,True))
        # Even native ownership rollback would not authorize reclaim while
        # a previously published node might deliver a callback later.
        self.assertFalse(permitted_reclaim(
            NativeReceipt(101,Ack.PUBLISHED,True,True),False
        ))

    def test_dropped_receipt_alone_cannot_free_foreign_retains(self):
        cases = [
            (False, False, False),
            (False, True, False),
            (True, False, False),
            (True, True, True),
        ]
        for balanced, no_future, expected in cases:
            with self.subTest(balanced=balanced,no_future=no_future):
                receipt = NativeReceipt(101,Ack.DROPPED,balanced,no_future)
                self.assertEqual(permitted_reclaim(receipt,False),expected)

    def test_native_receipt_must_not_apply_to_another_ticket(self):
        ticket = 9
        other = NativeReceipt(10,Ack.DROPPED,True,True)
        self.assertNotEqual(ticket,other.ticket)
        # The caller MUST compare receipt.ticket to the held ticket.
        # This function models safety AFTER that identity check.
        self.assertFalse(permitted_reclaim(
            NativeReceipt(ticket,Ack.UNKNOWN,False,False),False
        ))

    def test_ack_and_callback_race_never_resurrects_record(self):
        # An ack emitted after the queue is linked may be observed AFTER
        # an independent worker executes its HTTP completion callback.
        # A host test can enumerate both orders; stock has no such ack.
        for ordering in permutations(("publish_ack","http_completion")):
            tracked = Tracking()
            for step in ordering:
                if step == "publish_ack":
                    tracked.mark_published()
                else:
                    tracked.on_http_completion()
            self.assertEqual(tracked.state,"complete",ordering)
            self.assertEqual(tracked.acks,1)
            self.assertEqual(tracked.deliveries,1)

    def test_unknown_ack_does_not_clear_ticket_in_any_failure_path(self):
        for branch in (Ack.UNKNOWN,Ack.PUBLISHED,Ack.DROPPED):
            with self.subTest(branch=branch):
                t = Tracking()
                # Even an explicit drop without native rollback is unsafe.
                receipt = NativeReceipt(55,branch,False,False)
                t.request_reclaim(receipt)
                self.assertEqual(t.state,"reserved")

    def test_callback_is_sole_current_reclaim_signal(self):
        actual = SHIM.read_text()
        callback = actual.split(
            "static void combo_consume_response_locked(void *msg,",1
        )[1].split("/* END STEP115 REQUEST HELPERS */",1)[0]
        self.assertIn("memset(r, 0, sizeof *r)",callback)
        invalidate = actual.split(
            "static void combo_cancel_all_requests_locked(void) {",1
        )[1].split("static int combo_claim_request_locked",1)[0]
        self.assertNotIn("memset(",invalidate)

if __name__ == "__main__":
    unittest.main(verbosity=2)
