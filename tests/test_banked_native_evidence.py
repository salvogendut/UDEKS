# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
A = ROOT/'bench/artifacts/2026-10-01-banked-native'
R = ROOT/'bench/results/2026-10-01-banked-native'


class BankedNativeEvidence(unittest.TestCase):
    def test_exact_artifacts_and_executable_bounds(self):
        for directory in (A, R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), expected)
        self.assertEqual(len((A/'banked-loader.bin').read_bytes()), 1635)
        for tag, base in ((3, 0x2300), (4, 0x3500)):
            image = (A/f'native{tag}.udx').read_bytes()
            self.assertEqual(image[:8], b'UDEX\0\1\1\0')
            self.assertEqual(len(image), 661+16)
            self.assertEqual([int.from_bytes(image[i:i+2], 'little') for i in (8,10,12,14)],
                             [base,661,7,base+2])

    def test_native_execution_reap_and_reload_on_both_disks(self):
        for suffix, drive in (('d64','1541'), ('d71','1571')):
            folder = R/('vice-'+suffix)
            report = json.loads((folder/'result.json').read_text())
            self.assertEqual(report['disk_sha256'], hashlib.sha256((A/('native-test.'+suffix)).read_bytes()).hexdigest())
            self.assertEqual(report['loader_sha256'], hashlib.sha256((A/'banked-loader.bin').read_bytes()).hexdigest())
            self.assertEqual(report['drive'], drive)
            self.assertFalse(report['load_only'])
            self.assertTrue(report['legacy_code_preserved'])
            self.assertTrue(report['console_alive'])
            native = [r for r in report['records'] if 'native_task' in r]
            self.assertEqual([r['native_task'] for r in native], [3,4,3])
            for record in native:
                tag = record['native_task']
                self.assertGreaterEqual(record['progress'], 8)
                self.assertEqual(record['value'], (tag*1000+tag*record['progress']) & 65535)
                self.assertEqual(record['exit_status'], 40+tag)
                self.assertTrue(record['guards_ok'])
                self.assertEqual(record['lowest_software_sp'], 0x8C47 if tag==3 else 0x8F47)
            calls = [r for r in report['records'] if 'selector' in r]
            for record in calls:
                self.assertTrue(record['request_preserved'])
                self.assertTrue(record['kernel_map_restored'])
            pairs = {(r['selector'],r['errno']) for r in calls}
            for selector in (0x43,0x44,0x83,0x84,0xC3,0xC4):
                self.assertIn((selector,16), pairs)
            self.assertIn((0x43,8), pairs)  # managed images remain load-only
            self.assertEqual(sum(r['selector']==0xC3 and r['errno']==22 for r in calls), 2)
            before = (folder/'zombie-before-parent-fault.bin').read_bytes()
            after = (folder/'zombie-after-parent-fault.bin').read_bytes()
            self.assertEqual(after, before[:2]+b'\2'+before[3:])
            waits = (folder/'reaped-waits.bin').read_bytes()[2:]
            for tag in (3,4):
                for name, size in (('task',8), ('context',11)):
                    self.assertEqual((folder/f'reaped-{name}{tag}.bin').read_bytes()[2:], bytes(size))
                self.assertEqual([waits[i*8+tag-1] for i in range(10)], [0]*10)
                for name, size in (('bottom',16), ('top',16), ('cpu-stack',1)):
                    self.assertEqual((folder/f'native{tag}-{name}.bin').read_bytes()[2:], b'\xA5'*size)
                self.assertEqual((folder/f'native{tag}-error.bin').read_bytes()[2:], b'\0')

    def test_legacy_calculator_and_graphics_regression(self):
        report = json.loads((R/'legacy/result.json').read_text())
        self.assertEqual(report['disk_sha256'], hashlib.sha256((A/'udeks.d64').read_bytes()).hexdigest())
        self.assertTrue(report['image_matches_disk'])
        self.assertTrue(report['shadow_matches_bitmap'])
        self.assertEqual([r['hundredths'] for r in report['records'] if 'expression' in r], [400,300,475])
        bitmap = (R/'legacy/bitmap.bin').read_bytes()
        shadow = (R/'legacy/shadow.bin').read_bytes()
        self.assertEqual(len(bitmap), 8002)
        self.assertEqual(bitmap[2:], shadow[2:])
