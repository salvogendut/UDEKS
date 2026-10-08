# SPDX-License-Identifier: GPL-3.0-or-later
"""The successful, lean-D64 file-command delivery (not the earlier fit spike)."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from storage_public_probe import files
from storage_mutation_layout import headroom
from build_d71 import sector_offset

A = ROOT/'bench/artifacts/2026-10-08-file-commands'
R = ROOT/'bench/results/2026-10-08-file-commands'


class FileCommandsDelivery(unittest.TestCase):
    def test_all_evidence_is_hash_checked(self):
        for directory in (A,R):
            names=set()
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                digest,name=line.split()
                self.assertNotIn(name,names); names.add(name)
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),digest)
            self.assertEqual(names,{p.name for p in directory.iterdir() if p.name!='SHA256SUMS'})

    def test_d64_omits_only_sprite_editor_and_has_working_space(self):
        disks={ext:files((A/('udeks.'+ext)).read_bytes()) for ext in ('d64','d71','d81')}
        self.assertEqual(disks['d71'],disks['d81'])
        self.assertEqual(disks['d64'],{n:v for n,v in disks['d71'].items() if n!=b'XSPRDEF.BIN'})
        self.assertIn(b'XSPRDEF.BIN',disks['d71'])
        disk=(A/'udeks.d64').read_bytes(); bam=sector_offset(18,0)
        self.assertEqual(sum(disk[bam+4+(t-1)*4] for t in range(1,36) if t!=18),31)

    def test_independent_commands_are_installed_in_every_format(self):
        for name,size in (('CP',1747),('MV',1747),('RM',1674)):
            command=(A/(name+'.BIN')).read_bytes()
            self.assertEqual(len(command),size)
            self.assertEqual(command[:8],b'UDEX\0\1\1\0')
            self.assertEqual(int.from_bytes(command[8:10],'little'),0x200)
            self.assertLessEqual(0x200+sum(int.from_bytes(command[i:i+2],'little') for i in (10,12)),0xb00)
            for ext in ('d64','d71','d81'):
                self.assertEqual(files((A/('udeks.'+ext)).read_bytes())[(name+'.BIN').encode()],command)

    def test_actual_service_fits_original_reservations(self):
        budget=headroom((A/'module.map').read_text())
        self.assertEqual(budget['code_total'],11)
        self.assertEqual(budget['BSS'],26)
        report=json.loads((R/'layout.json').read_text())
        self.assertTrue(report['link_passed'])
        self.assertEqual(report['with_backend'],budget)
        self.assertEqual(report['production'],budget)

    def test_public_vice_reports_match_exact_delivered_images(self):
        for drive,ext in ((1541,'d64'),(1571,'d71'),(1581,'d81')):
            report=json.loads((R/f'vice-{drive}.json').read_text())
            disk=(A/('udeks.'+ext)).read_bytes()
            self.assertEqual(report['disk_sha256'],hashlib.sha256(disk).hexdigest())
            self.assertEqual(report['original_files_unchanged'],len(files(disk)))
            self.assertEqual(report['created'],{})
            commands={check['command'] for check in report['checks']}
            for line in ('cp /hello /COPY','mv /COPY /RENAMED','rm /RENAMED',
                         'cp /EMPTY /EMPTY2','cp /BINARY /BINCP','rm /PERSIST'):
                self.assertIn(line,commands)
            self.assertEqual({check['boot'] for check in report['checks']},{0,1})

    def test_reference_and_sdk_machine_tests_are_preserved(self):
        self.assertIn('35320 differential cases OK',(R/'backend.log').read_text())
        self.assertIn('6193 differential cases OK',(R/'status.log').read_text())
        self.assertIn('pending/completion/abort/exhaustion OK',(R/'status.log').read_text())
        self.assertIn('PASS 24 SDK scenarios',(R/'check.log').read_text())

    def test_native_ordinary_gate_does_not_misrepresent_timer_stress(self):
        report=json.loads((R/'1986-ordinary.json').read_text())
        self.assertEqual(report['disk_sha256'],hashlib.sha256((A/'udeks.d64').read_bytes()).hexdigest())
        self.assertFalse(report['timer_nmi_stress'])
        self.assertEqual(report['phases'],['create','reboot'])
        self.assertIn('cp /binary /copy',(R/'1986-create.log').read_text())
        self.assertIn('save -c /nmitest 515',(R/'1986-reboot.log').read_text())
        self.assertIn('FAIL: public write command failed',(R/'1986-timer-stress-failure.log').read_text())
        source=(ROOT/'tools/1986_storage_write_smoke.inc').read_text()
        self.assertIn('byte(0xf285)!=3',source)  # loader failure cannot inherit exit=0
        self.assertIn('!console_contains(line)',source)
