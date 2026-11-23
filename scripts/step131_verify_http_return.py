#!/usr/bin/env python3
"""Verify *exact stock* ARM send-return branches before allowing slot reclamation.

Input must come from stock sdDongle after independent SHA-256 gate in the
Step 131 read-only extraction script. This parser alone does not authenticate
an ELF; it checks the exact instructions and ordering used in the proof.
"""
import argparse
from pathlib import Path
import re
import sys

# Address -> ARM little-endian instruction opcode. All captured from the
# SHA-256 verified AK3918AN stock sdDongle, not the OMKE MIPS build.
EXPECTED = {
    0xA698C: "0a00002c",  # message->0x410 NULL skips prep; success dispatch
    0xA69BC: "eb000bb5",  # request-preparation helper
    0xA69C0: "e2505000",  # subs r5, r0, #0
    0xA69C4: "0a00000e",  # beq a6a04 -> successful preparation
    0xA6A00: "ea00001b",  # b a6a74 (no enqueue; return error r5)
    0xA6A4C: "ebff7088",  # CFRetain(message), after error bypass
    0xA6A54: "ebff7086",  # CFRetain(client)
    0xA6A6C: "ebffeba3",  # dispatch_async_f at a1900
    0xA6A70: "e3a05000",  # mov r5, #0 on enqueued path
    0xA6A74: "e1a00005",  # mov r0, r5 common return
    0xA6A7C: "e8bd80f0",  # pop {r4,r5,r6,r7,pc}
}
INSTRUCTION = re.compile(r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+", re.M)


def verify(text: str) -> None:
    instructions = {int(address, 16): opcode.lower()
                    for address, opcode in INSTRUCTION.findall(text)}
    missing = [hex(address) for address in EXPECTED if address not in instructions]
    if missing:
        raise ValueError("Stock HTTP path missing instruction(s): " +
                         ", ".join(missing))
    wrong = [(hex(address), instructions[address], opcode)
             for address, opcode in EXPECTED.items()
             if instructions[address] != opcode]
    if wrong:
        raise ValueError("Unverified native HTTP opcodes: " + repr(wrong))

    error_check, early_exit = 0xA69C0, 0xA6A00
    retain_start, enqueue, success_return, common_exit = (
        0xA6A4C, 0xA6A6C, 0xA6A70, 0xA6A74)
    assert error_check < early_exit < retain_start < enqueue < success_return < common_exit


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("report", type=Path, help="Verified-stock objdump report")
    args = cli.parse_args()
    try:
        verify(args.report.read_text())
    except (ValueError, OSError) as exc:
        print("FAIL: Step 131 HTTP return audit:", exc, file=sys.stderr)
        sys.exit(1)
    print("PASS: exact native nonzero-return branch exits before both retains and enqueue")
    print("PASS: enqueued stock HTTP send sets return to zero before shared exit")
    print("NOTE: applies only to SHA-256 verified stock AK3918AN sdDongle")
