#!/usr/bin/env python3
"""Read-only ARM objdump path inventory for AK3918 outgoing SETUP.

Reports candidate control-flow paths leaving the injection-to-send sequence.
Not proof of safety or exact runtime behaviour. Does not modify firmware.
"""
import argparse
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import hashlib
import re

DEFAULT_HOOK = 0x2fadc
DEFAULT_SEND = 0x2fbb0
DEFAULT_START = 0x2f6b8
DEFAULT_END = 0x30310
CONDITIONS = {'eq', 'ne', 'cs', 'hs', 'cc', 'lo', 'mi', 'pl', 'vs', 'vc',
              'hi', 'ls', 'ge', 'lt', 'gt', 'le', 'al', 'nv'}
INSN_RE = re.compile(r'^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+([a-zA-Z][\w.]*)\s*(.*)$')
HEX_TARGET = re.compile(r'^\s*(?:#?0x)?([0-9a-fA-F]+)(?:\s|$|<)')


@dataclass(frozen=True)
class Insn:
    address: int
    mnemonic: str
    operands: str


def parse_objdump(source):
    """Parse ARM 32-bit GNU objdump lines; ignore headings and other text."""
    result = {}
    for line in source.splitlines():
        match = INSN_RE.match(line)
        if match:
            addr = int(match.group(1), 16)
            result[addr] = Insn(addr, match.group(3).lower(), match.group(4).strip())
    return result


def branch_target(insn):
    value = insn.operands
    if re.match(r'^(?:r(?:1[0-5]|[0-9])|lr|pc|ip|sp)(?:\s|$)', value, re.I):
        return None
    match = HEX_TARGET.match(value)
    return int(match.group(1), 16) if match else None


def kind(insn):
    mn = insn.mnemonic.split('.')[0]
    if mn in {'bl', 'blx'}:
        return 'call'
    if mn == 'bx' or (mn in {'mov', 'movs'} and insn.operands.startswith('pc,')):
        return 'indirect-exit'
    if mn in {'pop', 'ldmia', 'ldmfd'} and re.search(r'\bpc\b', insn.operands):
        return 'indirect-exit'
    if mn in {'b', 'bal'}:
        return 'jump'
    if mn.startswith('b') and mn[1:] in CONDITIONS:
        return 'conditional-jump'
    if mn in {'cbz', 'cbnz'}:
        return 'conditional-jump'
    return 'next'


def successors(insn):
    tag = kind(insn)
    next_addr = insn.address + 4
    if tag == 'indirect-exit':
        return [(None, 'return/indirect control transfer')]
    if tag in {'jump', 'conditional-jump'}:
        target = branch_target(insn)
        result = [(target, 'direct branch' if target is not None else 'unknown branch target')]
        if tag == 'conditional-jump':
            result.append((next_addr, 'conditional fallthrough'))
        return result
    return [(next_addr, 'call return/fallthrough' if tag == 'call' else 'fallthrough')]


def trace(insns, hook=DEFAULT_HOOK, send=DEFAULT_SEND,
          start=DEFAULT_START, end=DEFAULT_END, limit=100000):
    if hook not in insns or send not in insns:
        raise ValueError(f'missing required hook/send instruction: {hook:#x}, {send:#x}')
    if not (start <= hook < end and start <= send < end):
        raise ValueError('hook and send must be inside native range')
    todo = deque([(hook, (hook,))])
    visited = set()
    exits = []
    send_path = None
    while todo:
        addr, path = todo.popleft()
        if addr == send:
            if send_path is None:
                send_path = path
            continue
        if addr in visited:
            continue
        visited.add(addr)
        if len(visited) > limit:
            raise ValueError('control-flow complexity limit exceeded')
        insn = insns.get(addr)
        if insn is None:
            exits.append((addr, 'missing instruction', path))
            continue
        for dest, reason in successors(insn):
            if dest is None:
                exits.append((addr, reason, path))
            elif dest < start or dest >= end:
                exits.append((addr, f'{reason} outside native range to {dest:#x}', path))
            elif dest not in insns:
                exits.append((addr, f'{reason} to missing {dest:#x}', path))
            elif dest not in visited:
                todo.append((dest, path + (dest,)))
    return {'reachable': len(visited), 'send_path': send_path, 'exits': exits}


def compact_path(path, max_count=24):
    if len(path) <= max_count:
        return ' -> '.join(f'{a:#x}' for a in path)
    return ' -> '.join(f'{a:#x}' for a in path[:12]) + (
        f' -> ... ({len(path) - max_count} omitted) ... -> ') + (
        ' -> '.join(f'{a:#x}' for a in path[-12:]))


def report(raw, hook=DEFAULT_HOOK, send=DEFAULT_SEND,
           start=DEFAULT_START, end=DEFAULT_END):
    parsed = parse_objdump(raw)
    sub = {a: inst for a, inst in parsed.items() if start <= a < end}
    output = trace(sub, hook=hook, send=send, start=start, end=end)
    lines = [
        '# Step 122 — conservative native request control-flow inventory',
        '',
        f'Disassembly text SHA-256: {hashlib.sha256(raw.encode()).hexdigest()}',
        f'Native range {start:#x}..{end:#x}; injection hook {hook:#x}; HTTP send {send:#x}.',
        f'Parsed range instructions: {len(sub)}; reachable non-send instructions: {output["reachable"]}.',
        '',
        'This is a **read-only diagnostic, not a safety certificate**. Calls are assumed',
        'to return; ARM instruction predication, indirect control flow, runtime effects,',
        'memory aliasing, reentrancy, exceptions and multi-thread races are not modeled.',
        'A potential bypass is NOT proof of an observed failure. No bypass here is NOT proof of safety.',
        '',
        '## Reachability of the native send site',
        '',
        'Send instruction reachable in this model: **YES**' if output['send_path'] else
        'Send instruction reachable in this model: **NOT DEMONSTRATED**',
    ]
    if output['send_path']:
        lines.extend(['', f'Sample route: {compact_path(output["send_path"])}'])
    lines.extend(['', '## Candidate paths leaving without visiting send', ''])
    if not output['exits']:
        lines.append('No such path found by this limited model (NOT proof of safety).')
    else:
        lines.append(f'Terminals: {len(output["exits"])}. Up to 24 distinct examples:')
        seen = set()
        for address, reason, path in output['exits']:
            key = (address, reason)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f'- {address:#x}: {reason}; path {compact_path(path)}')
            if len(seen) >= 24:
                break
    lines.extend(['', '## Native branches/calls between hook and send', ''])
    for address in sorted(sub):
        inst = sub[address]
        if hook <= address < send and kind(inst) in {
                'jump', 'conditional-jump', 'call', 'indirect-exit'}:
            lines.append(f'- {address:#x}: {inst.mnemonic} {inst.operands}')
    lines.extend(['', '**NO FLASH:** request identity and teardown/send ordering remain unverified.', ''])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disassembly', type=Path, help='Step 121 objdump text report')
    parser.add_argument('--output', type=Path, help='Markdown report; stdout if omitted')
    parser.add_argument('--hook', type=lambda s: int(s, 0), default=DEFAULT_HOOK)
    parser.add_argument('--send', type=lambda s: int(s, 0), default=DEFAULT_SEND)
    parser.add_argument('--start', type=lambda s: int(s, 0), default=DEFAULT_START)
    parser.add_argument('--end', type=lambda s: int(s, 0), default=DEFAULT_END)
    args = parser.parse_args()
    result = report(args.disassembly.read_text(errors='replace'),
                    hook=args.hook, send=args.send,
                    start=args.start, end=args.end)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + '\n')
        print(f'Step 122 read-only report: {args.output}')
    else:
        print(result)


if __name__ == '__main__':
    main()
