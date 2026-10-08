# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from default_service_layout import layouts, disk_files
from native_app_layout import check_coexistence, fitting_allocations
from service_image import validate

A = ROOT/'bench/results/2026-10-09-default-time'


class DefaultServiceEvidence(unittest.TestCase):
    def report(self,name):
        return json.loads((A/name).read_text())

    def test_evidence_integrity_clean_build_and_upgrade_parity(self):
        for row in (A/'SHA256SUMS').read_text().splitlines():
            digest,name = row.split('  ',1)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        clean = self.report('build.json')
        upgrade = self.report('migration.json')
        self.assertTrue(clean['clean_matches_worktree'])
        self.assertEqual(hashlib.sha256((A/'inputs.json').read_bytes()).hexdigest(),clean['input_manifest_sha256'])
        for name in ('no_clean','upgrade_matches_worktree','noop'):
            self.assertTrue(upgrade[name])
        self.assertEqual(upgrade['base'],'9eda8ba06a2a5965c9d5ad14943838d10c2e30cf')
        for name in upgrade['objects_before']:
            self.assertNotEqual(upgrade['objects_before'][name],upgrade['objects_after'][name])
        for fmt in ('d64','d71','d81'):
            self.assertEqual(clean['disks'][fmt]['sha256'],upgrade['disks'][fmt]['sha256'])

    def test_actual_layouts_and_vectors_remain_valid(self):
        maps = [(A/f'layout/udeks-8502{s}.map').read_text() for s in ('','-panic-probe')]
        images = [(A/f'layout/udeks-8502{s}.bin').read_bytes() for s in ('','-panic-probe')]
        self.assertEqual(layouts(*maps,images),self.report('build.json')['variants'])

    def test_published_files_boot_service_and_four_app_admission(self):
        for fmt in ('d64','d71','d81'):
            data = (ROOT/f'build/udeks.{fmt}').read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),self.report('build.json')['disks'][fmt]['sha256'])
            files = disk_files(data,fmt)
            for name in ('SVC.BIN','TIME.SVC'):
                self.assertEqual(files[name],(0x81,(A/name).read_bytes()))
            self.assertEqual(files['RC.ETC'],(0x81,(ROOT/'user/etc/rc').read_bytes()))
            self.assertEqual('XSPRDEF.BIN' in files,fmt!='d64')
            self.assertEqual(check_coexistence({name:fitting_allocations(files[name][1])
                for name in ('XCLOCK.BIN','XWAVE.BIN','XCALC.BIN','XDRAW.BIN')}),24)

    def test_all_formats_run_exact_module_and_disk_only_replacement(self):
        for fmt in ('d64','d71','d81'):
            result = self.report(fmt+'/report.json')
            self.assertEqual(result['source_disk_sha256'],self.report('build.json')['disks'][fmt]['sha256'])
            self.assertEqual((A/fmt/'installed-image.bin').read_bytes(),(A/'TIME.SVC').read_bytes())
            self.assertEqual(validate((A/fmt/'replacement-image.bin').read_bytes())['revision'],2)
            self.assertEqual(result['commands'][-1]['command'],'cat /hello')
            self.assertEqual(result['commands'][-1]['exit'],0)

    def test_failure_modes_preserve_shell_and_service_recovery(self):
        for mode in ('missing','corrupt','shell-missing','shell-corrupt'):
            result = self.report(mode+'/report.json')
            self.assertEqual(result['source_disk_sha256'],self.report('build.json')['disks']['d64']['sha256'])
            commands = result['commands']
            self.assertTrue(any('time: offline' in r['console'] for r in commands))
            self.assertTrue(any('load ' in r['command'] and r['exit']==0 for r in commands))
            self.assertIn('HELLO UDEKS',commands[-1]['console'])
            if mode.startswith('shell-'):
                self.assertEqual((A/mode/'boot-source.bin').read_bytes(),
                                 bytes((2,11 if mode=='shell-missing' else 4,8)))
                self.assertTrue(any(r['command']=='mount 8 /mnt' and r['exit']==0 for r in commands))

    def test_native_input_and_four_app_regression_use_published_images(self):
        native = self.report('1986/result.json')
        self.assertEqual(native['disk_sha256'],self.report('build.json')['disks']['d64']['sha256'])
        self.assertEqual(native['exit_status'],0)
        self.assertTrue(native['disk_service'])
        self.assertIn('PASS native 1986 disk-service RC/date/clock/drag/stop/reload/input',
                      (A/'1986/run.log').read_text())
        four = self.report('four-native/result.json')
        self.assertEqual(four['disk_sha256'],self.report('build.json')['disks']['d81']['sha256'])
        self.assertTrue(any(r.get('check')=='four-resized-pixels' for r in four['checks']))
        self.assertEqual(four['checks'][-1]['command'],'echo four-slot cleanup passed')


if __name__ == '__main__':
    unittest.main()
