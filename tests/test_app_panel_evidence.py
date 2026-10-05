# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'bench/artifacts/2026-10-04-app-panel'
R=ROOT/'bench/results/2026-10-04-app-panel'
ROWS={
    'boot':{1:'RUNNING',2:'NONE'},
    'two-clocks':{1:'RUNNING',2:'xinit',3:'nclock',4:'clock2'},
    'foreground-stopped':{2:'xinit',3:'nclock',4:''},
    'four-apps':{1:'RUNNING',2:'xinit',3:'xclock',4:'xwave',5:'nclock',6:'clock2'},
    'stopped':{1:'RUNNING',2:'NONE',3:'',4:'',5:'',6:''},
}


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class AppPanelEvidence(unittest.TestCase):
    def test_hashes(self):
        for folder in (A,R):
            for line in (folder/'SHA256SUMS').read_text().splitlines():
                checksum,name=line.split()
                self.assertEqual(digest(folder/name),checksum,name)

    def test_vice_real_vdc_text_and_attributes_all_formats(self):
        for suffix,drive in (('d64','1541'),('d71','1571'),('d81','1581')):
            folder=R/('vice-'+suffix)
            report=json.loads((folder/'result.json').read_text())
            self.assertEqual(report['drive'],drive)
            self.assertTrue(report['running_panel'])
            self.assertEqual(report['fixture_sha256'],digest(A/('native-clock.'+suffix)))
            for tag,rows in ROWS.items():
                raw=(folder/(tag+'-panel.bin')).read_bytes()
                self.assertEqual(raw[:2],b'\x00\x00')
                self.assertEqual(len(raw),4098)
                data=raw[2:]
                for row,text in rows.items():
                    expected=bytes(ord(c.upper())&31 if c.isalpha() else ord(c)
                                   for c in text.ljust(9))
                    address=0x04b2+row*80
                    self.assertEqual(data[address:address+9],expected,(suffix,tag,row))
                    self.assertEqual(data[address+0x800:address+0x809],
                                     bytes([0x80 if 2<=row<7 else 0])*9)

    def test_1986_before_fails_and_both_drive_models_pass(self):
        before=json.loads((R/'1986-before/result.json').read_text())
        self.assertEqual(before['exit_status'],1)
        self.assertIn('panel row 1: '+'12 '*9,(R/'1986-before/run.log').read_text())
        for suffix,drive in (('d64',1571),('d81',1581)):
            folder=R/('1986-'+suffix)
            report=json.loads((folder/'result.json').read_text())
            self.assertEqual(report['exit_status'],0)
            self.assertEqual(report['drive'],drive)
            self.assertTrue(report['raw_iec'] and report['native_clock'])
            self.assertEqual(report['test_disk_sha256'],digest(A/('native-clock.'+suffix)))
            log=(folder/'run.log').read_text()
            self.assertNotIn('FAIL:',log)
            self.assertIn('PASS native clock:',log)
            self.assertIn('PASS running panel:',log)
            for text in ('RUNNING','NONE','xinit','nclock','clock2','xclock','xwave'):
                self.assertIn('expected '+text+'\n',log)


if __name__=='__main__': unittest.main()
