# SPDX-License-Identifier: GPL-3.0-or-later
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from service_image import TIME_BASE, TIME_LIMIT


class ServiceCommandTests(unittest.TestCase):
    def test_real_c_loader_with_failure_injection(self):
        with tempfile.TemporaryDirectory(prefix='udeks-svc-') as folder:
            binary = Path(folder)/'check'
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                '-D__fastcall__=', '-DUDEKS_SERVICE_CLIENT_TEST', '-Iuser/include',
                'tests/fixtures/service_client.c', 'user/bin/svc.c', '-o', str(binary)], cwd=ROOT, check=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn('PASS 17', result.stdout)

    def test_console_slot_constants_match_the_image_contract(self):
        header = (ROOT/'user/include/udeks/service.h').read_text()
        for name, value in (('BASE', TIME_BASE), ('LIMIT', TIME_LIMIT)):
            found = re.search(r'UDEKS_SERVICE_'+name+r'\s+0x([0-9a-f]+)u', header)
            self.assertIsNotNone(found)
            self.assertEqual(int(found[1], 16), value)


if __name__ == '__main__':
    unittest.main()
