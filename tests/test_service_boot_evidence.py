# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from service_image import validate

A = ROOT/'bench/results/2026-10-08-disk-service'


class DiskServiceEvidence(unittest.TestCase):
    def test_preserved_inputs_outputs_and_reports_are_checksummed(self):
        for line in (A/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        build=json.loads((A/'build.json').read_text())
        self.assertEqual(hashlib.sha256((A/'inputs.json').read_bytes()).hexdigest(),build['input_manifest_sha256'])

    def test_all_formats_execute_exact_module_and_disk_only_replacement(self):
        build=json.loads((A/'build.json').read_text())
        original=(A/'TIME.SVC').read_bytes()
        self.assertEqual(validate(original)['revision'],1)
        for fmt,drive in (('d64','1541'),('d71','1571'),('d81','1581')):
            report=json.loads((A/fmt/'report.json').read_text())
            self.assertEqual(report['source_disk_sha256'],build['disks'][fmt]['sha256'])
            self.assertEqual(report['drive'],drive)
            self.assertEqual((A/fmt/'installed-image.bin').read_bytes(),original)
            replacement=(A/fmt/'replacement-image.bin').read_bytes()
            self.assertEqual(validate(replacement)['revision'],2)
            self.assertEqual([i for i,(a,b) in enumerate(zip(original,replacement)) if a!=b],[16,18])
            commands=report['commands']
            self.assertTrue(any(r['command']=='date' and r['exit']==1 for r in commands))
            self.assertTrue(any(r['command']=='svc load' and r['exit']==1 for r in commands))
            self.assertTrue(any(r['command']=='svc load /TIME2.SVC' and r['exit']==0 for r in commands))
            self.assertEqual(commands[-1]['command'],'cat /hello')

    def test_failed_boot_modules_recover_and_native_input_run_completes(self):
        for mode in ('missing','corrupt'):
            report=json.loads((A/mode/'report.json').read_text())
            self.assertEqual(report['mode'],mode)
            commands=report['commands']
            self.assertIn('time: offline',commands[0]['console'])
            self.assertEqual(commands[1]['exit'],1)
            self.assertEqual(commands[2]['exit'],1)
            self.assertEqual(commands[3]['command'],'svc load /TIME2.SVC')
            self.assertEqual(commands[3]['exit'],0)
        native=json.loads((A/'1986/result.json').read_text())
        build=json.loads((A/'build.json').read_text())
        self.assertEqual(native['disk_sha256'],build['disks']['d64']['sha256'])
        self.assertTrue(native['disk_service'])
        self.assertEqual(native['exit_status'],0)
        self.assertIn('PASS native 1986 disk-service RC/date/clock/drag/stop/reload/input',
                      (A/'1986/run.log').read_text())


if __name__ == '__main__':
    unittest.main()
