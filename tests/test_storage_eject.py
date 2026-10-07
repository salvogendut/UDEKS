# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_d81 as d81
from add_disk_apps import add_apps
from storage_failure_probe import audit,make_data

RESULTS=ROOT/'bench/results/2026-10-07-storage-eject-1986'
ARTIFACTS=ROOT/'bench/artifacts/2026-10-07-storage-acceptance'


class NativeEjectionEvidence(unittest.TestCase):
    def test_collector_accepts_absent_aborted_file_and_reproduces_report(self):
        spec=importlib.util.spec_from_file_location('eject_builder',ROOT/'tools/1986_storage_smoke_build.py')
        builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        expected=json.loads((RESULTS/'result.json').read_text())
        with patch.object(builder.subprocess,'check_output',side_effect=[expected['emulator_revision']+'\n','']):
            report=builder.collect_ejection(RESULTS,(ARTIFACTS/'udeks.d81').read_bytes(),
                                          (ARTIFACTS/'WHOLD.BIN').read_bytes(),Path('unused-emulator'))
        self.assertEqual(report,expected)

    def test_preserved_hashes_and_unmodified_emulator(self):
        for line in (RESULTS/'SHA256SUMS').read_text().splitlines():
            digest,path=line.split(maxsplit=1)
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)
        report=json.loads((RESULTS/'result.json').read_text())
        self.assertEqual(report['emulator_tracked_changes'],'')
        self.assertEqual(report['drive'],1581)
        self.assertEqual(report['unit'],9)
        self.assertEqual(report['phases'],['eject','reboot'])
        self.assertEqual(report['write_error'],5)
        self.assertEqual(report['accepted'],0)
        self.assertEqual(report['close_error'],5)
        self.assertEqual(report['generation_after'],(report['generation_before']+1)&255)
        self.assertEqual(report['cleanup_error'],0)

    def test_media_contents_and_post_reboot_readback(self):
        report=json.loads((RESULTS/'result.json').read_text())
        before=(RESULTS/'data-before.d81').read_bytes()
        after=(RESULTS/'data.d81').read_bytes()
        self.assertEqual(before,make_data('1581'))
        self.assertEqual(hashlib.sha256(before).hexdigest(),report['before_sha256'])
        self.assertEqual(hashlib.sha256(after).hexdigest(),report['after_sha256'])
        self.assertEqual(audit(before,after,{'OWNER2','RECOVER','OWNER4'}),report['files'])
        self.assertEqual(set(report['files']),{'RECOVER','OWNER4'})
        for entry in d81.entries(after,d81.sector_offset,40,3):
            if entry[3:19].rstrip(b'\xa0') in (b'KEEP',b'RECOVER',b'OWNER4'):
                self.assertEqual(entry[0],0x81)
                self.assertEqual(d81.file_bytes(after,entry,d81.sector_offset),bytes(range(24)))
        source=(ARTIFACTS/'udeks.d81').read_bytes()
        program=(ARTIFACTS/'WHOLD.BIN').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),report['source_disk_sha256'])
        self.assertEqual(hashlib.sha256(program).hexdigest(),report['program_sha256'])
        system=(RESULTS/'test.d81').read_bytes()
        self.assertEqual(system,add_apps(source,[('WHOLD.BIN',program)]))
        self.assertEqual(hashlib.sha256(system).hexdigest(),report['system_disk_sha256'])
        log=(RESULTS/'reboot.log').read_text()
        for name in ('keep','recover','owner4'):
            self.assertIn('PASS save -c /mnt/'+name+' 24: save: verified',log)


if __name__=='__main__': unittest.main()
