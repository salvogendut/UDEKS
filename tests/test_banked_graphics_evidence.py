# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'bench/artifacts/2026-10-01-banked-calculator'
R=ROOT/'bench/results/2026-10-01-banked-calculator'


class BankedGraphicsEvidence(unittest.TestCase):
    def test_exact_artifacts_and_limits(self):
        for directory in (A,R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                digest,name=line.split()
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),digest)
        calc=(A/'xcalc.udx').read_bytes()
        self.assertEqual(calc[:8],b'UDEX\0\1\1\0')
        self.assertEqual([int.from_bytes(calc[n:n+2],'little') for n in (8,10,12,14)],
            [0x2300,3912,412,0x2300])
        self.assertEqual(len(calc),3928)
        self.assertEqual(len((A/'banked-loader.bin').read_bytes()),1792)
        self.assertEqual(len((A/'banked-graphics.bin').read_bytes()),1536)
        report=json.loads((R/'layout.json').read_text())
        self.assertEqual(report['resident_bridge_headroom'],19)
        self.assertEqual(report['calculator_current_allocation_spare'],284)

    def test_three_app_input_lifecycle_and_console_on_both_formats(self):
        for suffix,drive in (('d64','1541'),('d71','1571')):
            folder=R/('vice-'+suffix)
            report=json.loads((folder/'result.json').read_text())
            self.assertEqual(report['disk_sha256'],hashlib.sha256((A/('udeks.'+suffix)).read_bytes()).hexdigest())
            self.assertEqual(report['drive'],drive)
            self.assertTrue(report['native_banked'])
            self.assertTrue(report['image_matches_disk'])
            self.assertTrue(report['shadow_matches_bitmap'])
            records=report['records']
            self.assertEqual([r['hundredths'] for r in records if 'hundredths' in r],[400,300,475])
            self.assertIn(dict(drag_retains_image=True,close_and_reload=True,peer_windows=2),records)
            self.assertIn(dict(foreground_ctrl_c=True,peer_windows=2),records)
            self.assertIn(dict(desktop_closes_all=True,software_guards_ok=True),records)
            commands=[r['command'] for r in records if 'command' in r]
            self.assertEqual(commands[:3],['xclock &','xwave &','xcalc &'])
            self.assertIn('cowsay calculator',commands)
            self.assertIn('free',commands)
            self.assertEqual(commands[-1],'xinit -q')

    def test_raw_bank_captures_match_reports(self):
        for suffix in ('d64','d71'):
            folder=R/('vice-'+suffix)
            def data(name): return (folder/(name+'.bin')).read_bytes()[2:]
            self.assertEqual(data('loaded'),(A/'xcalc.udx').read_bytes()[16:])
            self.assertEqual(len(data('three-apps-bitmap')),8000)
            self.assertEqual(data('three-apps-bitmap'),data('three-apps-shadow'))
            self.assertEqual(data('retained-before-drag'),data('retained-after-drag'))
            self.assertEqual(int.from_bytes(data('value-after-drag'),'little',signed=True),475)
            for name in ('guard-low','guard-high'):
                self.assertEqual(data(name),b'\xa5'*16)
