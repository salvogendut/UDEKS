# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from window_drag_start import NAME
from graphics_raster_link_audit import segments
from window_cache_live import bitmap_oracle,validate_live_slot
ART=ROOT/'bench/artifacts'/NAME
RESULTS=ROOT/'bench/results'/NAME
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


class DragStartEvidenceTests(unittest.TestCase):
    def test_hashes_layout_and_clean_parallel_rebuild(self):
        for directory in (ART,RESULTS):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                value,name=line.split('  ',1)
                self.assertEqual(sha(directory/name),value,name)
        report=json.loads((ART/'build/report.json').read_text())
        for key in ('inputs_sha256','source_sha256'):
            for name,value in report[key].items():self.assertEqual(sha(ART/'inputs'/name),value,name)
        for fmt,value in report['disk_sha256'].items():self.assertEqual(sha(ART/f'build/udeks-cache.{fmt}'),value)
        clean=json.loads((RESULTS/'clean-build.json').read_text())
        self.assertEqual(clean['report_sha256'],sha(ART/'build/report.json'))
        self.assertEqual(clean['before'],clean['after'])
        self.assertEqual(clean['after'],report['disk_sha256'])
        self.assertEqual(report['remaining_padding'],20)
        self.assertEqual(report['transport_bytes'],377)
        self.assertEqual(report['manager_sizes']['CODE'],7762)
        self.assertEqual(report['manager_sizes']['HIGHBSS'],88)
        for variant in ('udeks-8502','udeks-8502-panic-probe'):
            path=ART/f'inputs/build/window-drag-start/repo/build/8502/{variant}.map'
            self.assertEqual(segments(path.read_text()),report['segments'])

    def test_clock_drag_timings_are_source_bound_and_mouse_moves_outline(self):
        comparison=json.loads((RESULTS/'drag-latency.json').read_text())
        runs={}
        for variant in ('partial','deferred'):
            run=json.loads((RESULTS/'latency'/variant/'run.json').read_text());runs[variant]=run
            for name,value in run['input_sha256'].items():
                if name.startswith('build/window-drag-start/'):
                    path=ART/'build'/Path(name).name
                elif name=='tools/window_drag_latency.py':path=ART/'inputs'/name
                else:
                    self.assertTrue(name.startswith('bench/artifacts/2026-09-29-window-cache-partial-manager/'))
                    path=ROOT/name
                self.assertEqual(sha(path),value,name)
            for name,key in (('native.c','source_sha256'),('native','runner_sha256')):
                self.assertEqual(sha(ART/'latency'/variant/name),run[key])
            source=(ART/'latency'/variant/'native.c').read_text()
            self.assertIn('clock outline did not track native mouse',source)
            self.assertIn('joyports_mouse_button(&machine->joyports,0,false,true)',source)
            if variant=='deferred':self.assertIn('clock_start <= 30',source)
            self.assertEqual(set(run['log_sha256']),{'d71','d64'})
            for fmt,value in run['log_sha256'].items():
                path=RESULTS/'latency'/variant/(fmt+'.log')
                self.assertEqual(sha(path),value)
                text=path.read_text()
                fields={name:int(frames) for name,frames in re.findall(
                    r'^(clock drag start|overlap clock drag start): frames=(\d+)$',text,re.M)}
                self.assertEqual(fields,comparison[variant][fmt])
                self.assertIn('command: echo clock drag alive -> accepted',text)
                self.assertIn('PASS: native clock-only/overlap drag-start timing and shutdown',text)
                self.assertEqual(fields['clock drag start'],17)
                self.assertEqual(fields['overlap clock drag start'],265 if variant=='partial' else 16)
        self.assertEqual(runs['partial']['provenance'],runs['deferred']['provenance'])

    def test_full_pixels_guards_input_and_restart_on_both_formats(self):
        module=(ROOT/'bench/artifacts/2026-09-29-window-cache-partial/build/bench/window-cache-partial/module.bin').read_bytes()
        reference=ROOT/'bench/results/2026-09-29-window-cache-partial-manager'
        for engine in ('1986','vice'):
            run=json.loads((RESULTS/(engine+'-run.json')).read_text())
            self.assertEqual(run['report_sha256'],sha(ART/'build/report.json'))
            self.assertEqual(set(run['results']),{'d71','d64'})
            for name,value in run['raw_sha256'].items():self.assertEqual(sha(RESULTS/name),value)
            for fmt in ('d71','d64'):
                get=lambda suffix:(RESULTS/f'{engine}-{fmt}-{suffix}.bin').read_bytes()
                self.assertFalse(any(get('guards')))
                window=get('window')
                if engine=='1986':
                    self.assertFalse(any(get('stack-guard')))
                    window=next(window[i:i+17] for i in range(0,68,17) if window[i:i+2]==b'\x01\x02')
                    path=RESULTS/f'1986-{fmt}.log'
                    self.assertEqual(sha(path),run['results'][fmt]['log_sha256'])
                    self.assertIn('PASS: live cached moves, full pixels, fallback, cancellation and restart',path.read_text())
                    for case in range(3):
                        for surface in ('shadow','bitmap'):
                            name=f'1986-{fmt}-clock-{case}-{surface}.bin'
                            self.assertEqual((RESULTS/name).read_bytes(),(reference/name).read_bytes())
                pixels=bitmap_oracle(get('shadow'),get('bitmap'),get('image'),window)
                self.assertEqual(pixels['geometry'],run['results'][fmt]['geometry'])
                if engine=='1986':validate_live_slot(get('slot'),module,pixels['geometry'][2],pixels['geometry'][3])

if __name__=='__main__':unittest.main()
