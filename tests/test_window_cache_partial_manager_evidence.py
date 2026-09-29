# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from window_cache_partial_manager import NAME
from window_cache_partial import NAME as PROVIDER
from window_cache_occlusion import clock_measurements
from window_cache_live import bitmap_oracle,validate_live_slot
from graphics_raster_link_audit import segments

ART=ROOT/'bench/artifacts'/NAME
RESULTS=ROOT/'bench/results'/NAME
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


class PartialManagerEvidenceTests(unittest.TestCase):
    def test_all_hashes_links_and_clean_rebuild(self):
        report=json.loads((ART/'build/report.json').read_text())
        for directory in (ART,RESULTS):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                value,name=line.split('  ',1)
                self.assertEqual(sha(directory/name),value,name)
        for key in ('inputs_sha256','source_sha256'):
            for name,value in report[key].items():self.assertEqual(sha(ART/'inputs'/name),value,name)
        for fmt,value in report['disk_sha256'].items():self.assertEqual(sha(ART/f'build/udeks-cache.{fmt}'),value)
        clean=json.loads((RESULTS/'clean-build.json').read_text())
        self.assertEqual(clean['report_sha256'],sha(ART/'build/report.json'))
        self.assertEqual(clean['before'],clean['after'])
        self.assertEqual(clean['after'],report['disk_sha256'])
        self.assertEqual(report['remaining_padding'],32)
        self.assertEqual(report['transport_bytes'],377)
        self.assertEqual(report['manager_sizes']['CODE'],7750)
        self.assertEqual(report['manager_sizes']['HIGHBSS'],88)
        for variant in ('udeks-8502','udeks-8502-panic-probe'):
            path=ART/f'inputs/build/window-cache-partial/repo/build/8502/{variant}.map'
            self.assertEqual(segments(path.read_text()),report['segments'])

    def test_runtime_binding_pixels_guards_and_live_provider(self):
        report_path=ART/'build/report.json'
        module=(ROOT/'bench/artifacts'/PROVIDER/'build/bench/window-cache-partial/module.bin').read_bytes()
        for engine in ('1986','vice'):
            run=json.loads((RESULTS/(engine+'-run.json')).read_text())
            self.assertEqual(run['report_sha256'],sha(report_path))
            self.assertEqual(set(run['results']),{'d71','d64'})
            for name,value in run['raw_sha256'].items():self.assertEqual(sha(RESULTS/name),value)
            for fmt in ('d71','d64'):
                self.assertEqual(run['results'][fmt]['pixels'],17472)
                self.assertFalse(any((RESULTS/f'{engine}-{fmt}-guards.bin').read_bytes()))
                if engine=='1986':
                    self.assertFalse(any((RESULTS/f'1986-{fmt}-stack-guard.bin').read_bytes()))
                    windows=(RESULTS/f'1986-{fmt}-window.bin').read_bytes()
                    window=next(windows[i:i+17] for i in range(0,68,17) if windows[i:i+2]==b'\x01\x02')
                    log=RESULTS/f'1986-{fmt}.log'
                    self.assertEqual(sha(log),run['results'][fmt]['log_sha256'])
                    self.assertIn('PASS: live cached moves, full pixels, fallback, cancellation and restart',log.read_text())
                else:window=(RESULTS/f'vice-{fmt}-window.bin').read_bytes()
                get=lambda suffix:(RESULTS/f'{engine}-{fmt}-{suffix}.bin').read_bytes()
                pixels=bitmap_oracle(get('shadow'),get('bitmap'),get('image'),window)
                self.assertEqual(pixels['geometry'],run['results'][fmt]['geometry'])
                if engine=='1986':validate_live_slot(get('slot'),module,pixels['geometry'][2],pixels['geometry'][3])

    def test_comparison_is_bound_and_every_canvas_matches(self):
        comparison=json.loads((RESULTS/'comparison.json').read_text())
        reference=ROOT/'bench/results/2026-09-28-window-cache-occlusion'
        allowed={str((reference/'SHA256SUMS').relative_to(ROOT))}
        def archived(name):
            if name.startswith('build/window-cache-partial/'):
                leaf=Path(name).name
                return ART/'build/report.json' if leaf=='report.json' else RESULTS/leaf
            self.assertTrue(name.startswith(str(reference.relative_to(ROOT))+'/'))
            return ROOT/name
        for fmt in ('d71','d64'):
            new=clock_measurements((RESULTS/f'1986-{fmt}.log').read_text())
            old=clock_measurements((reference/f'1986-{fmt}.log').read_text())
            self.assertEqual(comparison['values'][fmt],{'before':old,'after':new})
            self.assertEqual(new[2]['frames'],195)
            self.assertEqual(new[2]['pages'],23)
            self.assertEqual(old[:2],new[:2])
            for directory in (reference,Path('build/window-cache-partial')):
                prefix=str(directory.relative_to(ROOT)) if directory.is_absolute() else str(directory)
                for case in range(3):
                    for surface in ('shadow','bitmap'):
                        allowed.add(f'{prefix}/1986-{fmt}-clock-{case}-{surface}.bin')
                allowed.add(f'{prefix}/1986-{fmt}.log')
            for case in range(3):
                values=[(directory/f'1986-{fmt}-clock-{case}-{surface}.bin').read_bytes()
                    for directory in (reference,RESULTS) for surface in ('shadow','bitmap')]
                self.assertEqual(len(values[0]),8000)
                self.assertTrue(all(v==values[0] for v in values))
        allowed.update(('build/window-cache-partial/report.json','build/window-cache-partial/1986-run.json'))
        self.assertEqual(set(comparison['inputs_sha256']),allowed)
        for name,value in comparison['inputs_sha256'].items():self.assertEqual(sha(archived(name)),value)


if __name__=='__main__':unittest.main()
