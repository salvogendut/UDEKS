# SPDX-License-Identifier: GPL-3.0-or-later
"""First #47 increment: writable boot root and PRIVATE mutation mechanism."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from storage_mutate_probe import SAMPLES, fixture, read_files
from build_scheduler_overlay import map_segments

A = ROOT/'bench/artifacts/2026-10-08-storage-files'
R = ROOT/'bench/results/2026-10-08-storage-files'
digest = lambda data: hashlib.sha256(data).hexdigest()
report = lambda name: json.loads((R/(name+'.json')).read_text())


class StorageFilesCheckpoint(unittest.TestCase):
    def test_archived_hashes_and_private_probe_identity(self):
        for folder in (A,R):
            for line in (folder/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(digest((folder/name).read_bytes()), expected)
        program = (A/'mutate.prg').read_bytes()
        self.assertEqual(program[:2], b'\0\x28')
        for drive in ('1541','1571','1581'):
            self.assertEqual(report('mutate-'+drive)['program_sha256'], digest(program))

    def test_boot_writable_without_remount_and_readonly_enforcement(self):
        disk_hash = digest((A/'udeks.d64').read_bytes())
        self.assertEqual(report('public-1541')['disk_sha256'], disk_hash)
        self.assertEqual(report('native-1986')['disk_sha256'], disk_hash)
        for drive in ('1541','1571','1581'):
            result = report('public-'+drive)
            self.assertEqual(result['created']['BOOTRW'],24)
            first = [row for row in result['checks'] if row['boot']==0]
            commands = [row['command'] for row in first]
            self.assertEqual(commands[:2], ['df','save /BOOTRW 24'])
            self.assertIn('Read-write mount',first[0]['console'])
            self.assertEqual(first[1]['status'],0)
            self.assertTrue(any('Read-only filesystem' in row['console'] and row['status']==1 for row in first))
            reboot = [row for row in result['checks'] if row['boot']==1]
            self.assertTrue(any(row['command']=='save -c /BOOTRW 24' and row['status']==0 for row in reboot))
            self.assertEqual(result['original_files_unchanged'],23)
        native = report('native-1986')
        self.assertEqual(native['phases'],['create','reboot'])
        self.assertEqual(native['existing_files_unchanged'],23)
        recovery = report('recovery')
        self.assertTrue(recovery['recovery'])
        self.assertTrue(recovery['driver_intact'])
        self.assertIn('/mnt/RECOVER recovery',[row['command'] for row in recovery['commands']])

    def test_private_mutations_preserve_all_file_bytes_and_types(self):
        expected = SAMPLES | {'COPYPRG':SAMPLES['SRCPRG'], 'COPYEMPTY':SAMPLES['EMPTY'],
                              'LONG1234567890AB':SAMPLES['LONGSOURCE123456']}
        for drive, suffix in (('1541','d64'),('1571','d71'),('1581','d81')):
            result = report('mutate-'+drive)
            phases = result['phases']
            self.assertEqual(result['before_sha256'],digest(fixture(drive)))
            self.assertEqual(phases[0]['disk_sha256'],result['before_sha256'])
            self.assertEqual(bytes.fromhex(phases[0]['record'])[:4],bytes((2,1,30,30)))
            self.assertEqual(bytes.fromhex(phases[1]['record'])[:4],bytes((2,11,0,0)))
            disk = (R/f'mutate-{drive}.{suffix}').read_bytes()
            self.assertEqual(digest(disk),phases[1]['disk_sha256'])
            self.assertEqual(read_files(disk,drive),expected)
            self.assertIn('not installed',result['scope'])
            self.assertIn('not DOS COPY',result['empty_copy'])

    def test_production_service_budget_is_not_silently_expanded(self):
        segments = map_segments((A/'storage.map').read_text())
        self.assertEqual(segments['BSS'],(0xe000,0xe17f,384))
        free = sum(limit-segments[name][1]-1 for name,limit in (
            ('CODE',0x1880),('STORAGECODE',0xc600),('IECCODE',0xe900),('STORAGEHIGH',0xff00)))
        self.assertEqual(free,175)
