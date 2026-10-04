# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from add_disk_apps import add_apps
from build_d81 import build_image

A=ROOT/'bench/artifacts/2026-10-04-console-d81'
R=ROOT/'bench/results/2026-10-04-console-d81'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class ConsoleD81Evidence(unittest.TestCase):
    def test_exact_images_examples_and_three_format_results(self):
        for folder in (A,R):
            for row in (folder/'SHA256SUMS').read_text().splitlines():
                expected,name=row.split()
                self.assertEqual(digest(folder/name),expected,name)
        console=(A/'ARGS.BIN').read_bytes(); graphical=(A/'HELLO.BIN').read_bytes()
        self.assertEqual(console[:8],b'UDEX\0\1\1\0')
        self.assertEqual(graphical[:8],b'UDEX\0\2\1\0')
        self.assertEqual(build_image((A/'udeks.d71').read_bytes()),(A/'udeks.d81').read_bytes())
        for suffix,drive in (('d64','1541'),('d71','1571'),('d81','1581')):
            disk=A/('udeks.'+suffix); demo=A/('apps-demo.'+suffix)
            self.assertEqual(add_apps(disk.read_bytes(),[('ARGS.BIN',console),('AGAIN.BIN',console),
                              ('HELLO.BIN',graphical),('SECOND.BIN',graphical)]),demo.read_bytes())
            folder=R/('vice-'+suffix); report=json.loads((folder/'result.json').read_text())
            self.assertEqual(report['drive'],drive)
            self.assertEqual(report['disk_sha256'],digest(disk))
            self.assertEqual(report['fixture_sha256'],digest(demo))
            self.assertEqual(report['console_sha256'],digest(A/'ARGS.BIN'))
            self.assertEqual(report['graphical_sha256'],digest(A/'HELLO.BIN'))
            for field in ('arbitrary_names','arguments','stdout_stderr','exit_status',
                          'bss_reload','lazy_graphics','foreground_ctrl_c_both_slots',
                          'console_with_four_windows'):
                self.assertTrue(report[field],field)
            records={r['command']:r for r in report['records']}
            for command in ('args alpha beta','again renamed','args while graphics run','args reload','args final'):
                self.assertEqual(records[command]['exit'],37)
                self.assertIn('fresh BSS',records[command]['console'])
            self.assertIn('[alpha]',records['args alpha beta']['console'])
            self.assertIn('[beta]',records['args alpha beta']['console'])
            self.assertIn('stderr works',records['args alpha beta']['console'])
            self.assertEqual((folder/'vic-before.bin').read_bytes(),(folder/'vic-after.bin').read_bytes())
            self.assertIn((folder/'peer-after-interrupt.bin').read_bytes()[2],(2,3,4))

    def test_regressions_and_clean_build(self):
        report=json.loads((R/'generic-d64/result.json').read_text())
        self.assertEqual(report['disk_sha256'],digest(A/'udeks.d64'))
        self.assertEqual(report['fixture_sha256'],digest(A/'generic-qualification.d64'))
        self.assertTrue(report['drag_close_reuse'] and report['legacy_stop_safe'])
        prefix=R/'generic-d64'
        self.assertEqual((prefix/'two-generic-windows-bitmap.bin').read_bytes()[2:],
                         (prefix/'two-generic-windows-shadow.bin').read_bytes()[2:])
        report=json.loads((R/'native-input-d64/result.json').read_text())
        self.assertEqual(report['exit_status'],0)
        self.assertEqual(report['disk_sha256'],digest(A/'udeks.d64'))
        self.assertEqual(report['test_disk_sha256'],digest(A/'native-test.d64'))
        self.assertTrue(report['four_apps'] and report['raw_iec'])
        self.assertIn('PASS four apps: native input',(R/'native-input-d64/run.log').read_text())
        report=json.loads((R/'typed-boot-d81/result.json').read_text())
        self.assertEqual(report['disk_sha256'],digest(A/'udeks.d81'))
        self.assertEqual((report['entry'],report['drive']),('BASIC BOOT','1581'))
        report=json.loads((R/'clean-result.json').read_text())
        self.assertTrue(report['byte_identical'])
        self.assertEqual(len(report['sha256']),11)
        for name,value in report['sha256'].items():
            label=('storage-'+Path(name).name) if name.startswith('storage/') else Path(name).name
            self.assertEqual(digest(A/label),value)


if __name__=='__main__': unittest.main()
