#!/usr/bin/env python3
"""Static regression gate for the AK3918 experimental session-lifetime patch.

This does not prove correct vendor ABI signatures, object ownership or runtime
safety, and is not permission to flash firmware. It catches accidental
reintroduction of previously identified unsafe sink-thread patterns.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "altscreen.c"
text = SOURCE.read_text(encoding="utf-8")


def body_of(start_pattern: str) -> str:
    match = re.search(start_pattern, text, re.MULTILINE)
    if match is None:
        raise ValueError(f"missing expected declaration: {start_pattern}")
    opening = text.find("{", match.end())
    if opening == -1:
        raise ValueError(f"missing opening brace: {start_pattern}")
    depth = 0
    for pos in range(opening, len(text)):
        char = text[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1:pos]
    raise ValueError(f"unclosed function: {start_pattern}")


failures = []
try:
    sink_args = re.search(r"struct\s+sink_args\s*\{([^}]+)\}\s*;", text)
    if sink_args is None:
        failures.append("sink_args structure missing")
    else:
        fields = sink_args.group(1)
        if re.search(r"\bsession\b|\bconnid\b|void\s*\*", fields, re.IGNORECASE):
            failures.append("sink_args must not retain vendor session/connection pointers")
        if "struct sink_keys keys" not in fields:
            failures.append("sink_args must own a stream-key snapshot")
    sink = body_of(r"static\s+void\s*\*\s*sink_thread\s*\(void\s*arg\)")
    banned = (
        (r"\bsend_phone_cmd\s*\(", "delayed vendor phone-command dispatch"),
        (r"\bsession_send_command\s*\(", "direct delayed session command"),
        (r"\bget_stream_keys\s*\(", "asynchronous PairVerify key derivation"),
        (r"\bderive_screen\s*\(", "asynchronous legacy key derivation"),
        (r"\bsnapshot\s*\.\s*session\b", "borrowed session field"),
        (r"\bargs\s*->\s*session\b", "borrowed session argument"),
        (r"\bsession_is_current\s*\(", "raw-session identity checks in sink"),
    )
    for pattern, description in banned:
        if re.search(pattern, sink):
            failures.append(f"sink_thread contains {description}")
    for expected in ("wipe_sink_keys(&keys)", "generation_is_current(snapshot.generation)"):
        if expected not in sink:
            failures.append(f"sink_thread missing expected guard: {expected}")
    setup = body_of(r"int\s+shim_session_setup\s*\(void\s*session\s*,")
    for expected in (
        "snapshot_alt_keys(session, conn111, &alt_keys)",
        "wipe_sink_keys(&alt_keys)",
    ):
        if expected not in setup:
            failures.append(f"SETUP missing key snapshot or wipe: {expected}")
except ValueError as exc:
    failures.append(str(exc))

if failures:
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    sys.exit(1)

print("PASS: static sink-thread session-lifetime regression checks")
print("NOTE: compile, ABI, key correctness and runtime lifecycle remain unverified by this gate")
