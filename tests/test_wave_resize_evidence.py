# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from four_native_probe import check_wave_pixels

A=ROOT/'bench/artifacts/2026-10-05-wave-resize'
R=ROOT/'bench/results/2026-10-05-wave-resize'


class WaveResizeEvidence(unittest.TestCase):
    def test_artifact_and_result_hashes(self):
        for directory in (A,R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                digest,name=line.split()
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),digest,name)
        image=(A/'xwave.udx').read_bytes()
        self.assertEqual(int.from_bytes(image[10:12],'little')+int.from_bytes(image[12:14],'little'),3748)

    def test_native_mouse_no_input_completion_and_input_polling(self):
        before=(R/'before-1986/run.log').read_text()
        after=(R/'after-1986/run.log').read_text()
        pattern=r'resize published without further input after (\d+) PAL frames'
        self.assertEqual(list(map(int,re.findall(pattern,before))),[755,1399])
        self.assertEqual(list(map(int,re.findall(pattern,after))),[418,594])
        timings=re.findall(r'projection (\d+), maximum input-poll gap (\d+)',after)
        self.assertEqual(len(timings),2)
        for duration,gap in timings:
            self.assertTrue(1<int(duration)<=400)
            self.assertTrue(0<int(gap)<=16)
        for tag,disk in (('before-1986',ROOT/'bench/artifacts/2026-10-05-four-native/udeks.d64'),
                         ('after-1986',A/'udeks.d64')):
            report=json.loads((R/tag/'result.json').read_text())
            self.assertEqual(report['exit_status'],0)
            self.assertTrue(report['four_native'])
            self.assertEqual(report['disk_sha256'],hashlib.sha256(disk.read_bytes()).hexdigest())
            self.assertIn('PASS four native:',(R/tag/'run.log').read_text())

    def test_visible_new_grid_without_a_later_focus_event(self):
        for suffix in ('d64','d71','d81'):
            directory=R/('vice-'+suffix)
            report=json.loads((directory/'result.json').read_text())
            self.assertEqual(report['disk_sha256'],hashlib.sha256((A/('udeks.'+suffix)).read_bytes()).hexdigest())
            waves=[row['presents'] for row in report['checks'] if 'presents' in row]
            self.assertEqual(waves,[1,1,1,2,2,3,3,4,4,5,1])
            bitmap=(directory/'four-resized-bitmap.bin').read_bytes()[2:]
            self.assertEqual(bitmap,(directory/'four-resized-shadow.bin').read_bytes()[2:])
            check_wave_pixels(bitmap,44,44,256,146)
            with self.assertRaises(AssertionError):
                # Correct RAM transport alone is insufficient: reject the old
                # geometry (and a blank screen) as a visible-resize success.
                check_wave_pixels(bitmap,44,44,176,112)
            with self.assertRaises(AssertionError):
                check_wave_pixels(bytes(8000),44,44,256,146)
