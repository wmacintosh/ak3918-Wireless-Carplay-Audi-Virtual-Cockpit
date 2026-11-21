#!/usr/bin/env python3
"""Source-only regression checks for Step 121 Docker bash heredoc."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'step121_extract_native_request.sh'


class Step121ShellTests(unittest.TestCase):
    def test_container_script_executes_dump_with_apostrophes(self):
        source = SCRIPT.read_text()
        subprocess.run(['bash', '-n', str(SCRIPT)], check=True)
        self.assertIn('ak3918-buildroot:latest -s > "$TEMP_REPORT" <<', source)
        self.assertIn('  -v "$ROOT:/repo:ro"', source)
        self.assertIn('  -v ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro', source)
        match = re.search(
            r"<<'AK3918_READONLY'\n(.*?)\nAK3918_READONLY(?:\n|$)",
            source, re.DOTALL)
        self.assertIsNotNone(match, 'Container command must use a literal heredoc')
        body = match.group(1)
        subprocess.run(['bash', '-n', '-s'], input=body, text=True, check=True)
        self.assertIn("function's common cleanup", body)

        with tempfile.TemporaryDirectory(prefix='step121-shell-') as temp:
            root = Path(temp)
            stub = root / 'fake-objdump'
            input_file = root / 'stock-dummy'
            args_file = root / 'args.txt'
            input_file.write_text('not firmware; no real stock binary in CI')
            stub.write_text(
                '#!/bin/sh\n'
                'printf "%s\\n" "$*" >> "$AK_TEST_ARGS"\n'
                'printf "0002fadc: e1a00000 nop\\n0002fbb0: eb017baa bl a6974\\n"\n')
            stub.chmod(0o755)
            body = re.sub(r'^OBJDUMP=.*$', f'OBJDUMP={stub}', body, flags=re.MULTILINE)
            body = re.sub(r'^STOCK=.*$', f'STOCK={input_file}', body, flags=re.MULTILINE)
            env = dict(os.environ, AK_TEST_ARGS=str(args_file))
            result = subprocess.run(
                ['bash', '-s'], input=body, text=True,
                check=True, capture_output=True, env=env)
            self.assertEqual(result.stdout.count('===== '), 4)
            self.assertIn('COMPLETE NATIVE OUTGOING REQUEST AND CLEANUP', result.stdout)
            self.assertIn('HTTP SEND FUNCTION', result.stdout)
            calls = args_file.read_text().splitlines()
            self.assertEqual(len(calls), 4)
            self.assertIn('--start-address=0x2f6b8', calls[0])
            self.assertIn('--stop-address=0x30310', calls[0])
            self.assertIn('--start-address=0xa6974', calls[-1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
