#!/usr/bin/env python3
"""Unit tests for read-only ARM Step 122 path inventory."""
from pathlib import Path
import importlib.util
import sys
import unittest

FILE = Path(__file__).resolve().parents[1] / 'scripts' / 'step122_native_request_paths.py'
spec = importlib.util.spec_from_file_location('step122_native_request_paths', FILE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class TestStep122(unittest.TestCase):
    def test_parser_and_direct_branch(self):
        sample = '  2fadc:\teb019b14 \tbl\t9327c <native_array_ensure>\n'
        result = mod.parse_objdump(sample)
        self.assertEqual(result[0x2fadc].mnemonic, 'bl')
        self.assertEqual(mod.branch_target(result[0x2fadc]), 0x9327c)
        self.assertEqual(mod.kind(result[0x2fadc]), 'call')

    def test_success_and_error_bypass(self):
        sample = '''
2fadc: eb019b14 bl 9327c <array_ensure>
2fae0: 1a000002 bne 2faf0 <error>
2fae4: e1a00000 nop
2fae8: ea000003 b 2fafc <send_path>
2faec: e1a00000 nop
2faf0: e12fff1e bx lr
2faf4: e1a00000 nop
2faf8: e1a00000 nop
2fafc: ea00002b b 2fbb0 <send>
2fbb0: eb017baa bl a6974 <send>
'''
        outcome = mod.trace(mod.parse_objdump(sample))
        self.assertIsNotNone(outcome['send_path'])
        self.assertTrue(any(
            addr == 0x2faf0 and 'return' in reason
            for addr, reason, _ in outcome['exits']
        ))
        self.assertIn('NO FLASH', mod.report(sample))

    def test_incomplete_dump_does_not_hide_missing_instructions(self):
        sample = '''
2fadc: eb019b14 bl 9327c <array_ensure>
2fae0: e1a00000 nop
2fbb0: eb017baa bl a6974 <send>
'''
        outcome = mod.trace(mod.parse_objdump(sample))
        self.assertIsNone(outcome['send_path'])
        self.assertTrue(outcome['exits'])
        self.assertIn('missing', outcome['exits'][0][1])

    def test_indirect_register_not_interpreted_as_target(self):
        insn = mod.Insn(0x2fae0, 'bx', 'r3')
        self.assertIsNone(mod.branch_target(insn))
        self.assertEqual(mod.kind(insn), 'indirect-exit')


if __name__ == '__main__':
    unittest.main(verbosity=2)
