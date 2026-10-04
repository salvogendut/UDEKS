# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from native_clock_probe import clock_commands
from o65_to_udex import relocate_executable
A=ROOT/'bench/artifacts/2026-10-04-native-resize'
R=ROOT/'bench/results/2026-10-04-native-resize'

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

class NativeResizeEvidence(unittest.TestCase):
    def test_hashes_and_both_allocation_limits(self):
        for directory in (A,R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                checksum,name=line.split()
                self.assertEqual(digest(directory/name),checksum,name)
        image=(A/'NCLOCK.BIN').read_bytes()
        self.assertEqual(len(image),2770)
        self.assertLessEqual(len(image),2816)
        self.assertLessEqual(sum(int.from_bytes(image[n:n+2],'little') for n in (10,12)),2816)

    def test_scaled_retained_images_and_relocated_code_all_formats(self):
        image=(A/'NCLOCK.BIN').read_bytes()
        for suffix in ('d64','d71','d81'):
            directory=R/('vice-'+suffix)
            report=json.loads((directory/'result.json').read_text())
            self.assertTrue(report['resize'])
            self.assertEqual(report['fixture_sha256'],digest(A/('native-clock.'+suffix)))
            self.assertEqual(report['program_sha256'],digest(A/'NCLOCK.BIN'))
            checks={r['check']:r for r in report['records'] if 'check' in r}
            for tag,row in checks.items():
                expected=clock_commands(row['hour'],row['minute'],row['width'],row['height'])
                for kind in ('commands','retained'):
                    self.assertEqual((directory/(tag+'-'+kind+'.bin')).read_bytes()[2:],expected)
                self.assertEqual((directory/(tag+'-geometry.bin')).read_bytes()[2:],
                                 row['width'].to_bytes(2,'little')+bytes([row['height']]))
                base,capacity=(0x2300,0x1200) if row['slot']==3 else (0x3500,0xb00)
                self.assertEqual((directory/(tag+'-code.bin')).read_bytes()[2:],
                                 relocate_executable(image,base,capacity)[16:])
            for tag,expected in (('second-enlarged',(126,130)),('second-minimum',(48,48)),
                                 ('second-regrown',(126,130)),('first-enlarged',(180,140)),
                                 ('first-unaffected',(72,88)),('second-unaffected',(126,130))):
                self.assertEqual((checks[tag]['width'],checks[tag]['height']),expected)
            for a,b in (('first-set-time','first-after-drag'),('second-clock','second-after-drag')):
                # The preserved move occurred within one clock minute.
                self.assertEqual([checks[a][n] for n in ('hour','minute','presents')],
                                 [checks[b][n] for n in ('hour','minute','presents')])
            self.assertEqual((directory/'two-native-clocks-shadow.bin').read_bytes()[2:],
                             (directory/'two-native-clocks-bitmap.bin').read_bytes()[2:])

    def test_native_mouse_and_both_drive_geometries(self):
        for suffix,drive in (('d64',1571),('d81',1581)):
            directory=R/('1986-'+suffix)
            report=json.loads((directory/'result.json').read_text())
            self.assertEqual(report['exit_status'],0)
            self.assertEqual(report['drive'],drive)
            self.assertEqual(report['test_disk_sha256'],digest(A/('native-clock.'+suffix)))
            log=(directory/'run.log').read_text()
            self.assertNotIn('FAIL:',log)
            for phrase in ('PASS native resize:', 'PASS native clock:', 'PASS running panel:',
                           'clock task 4 geometry observed 126x130 expected 126x130',
                           'clock task 3 geometry observed 180x140 expected 180x140'):
                self.assertIn(phrase,log)

if __name__=='__main__': unittest.main()
