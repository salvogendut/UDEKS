# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from graphics_app_layout import glyph_overlay_layout,glyph_overlay_entrypoints
from gen_capability_imports import map_exports
from native_wave_probe import wave_paths
from native_worker_probe import expected_surface
from native_clock_probe import clock_commands
from o65_to_udex import pack_o65,relocate_executable
A=ROOT/'bench/artifacts/2026-10-04-native-wave'
R=ROOT/'bench/results/2026-10-04-native-wave'

def digest(data): return hashlib.sha256(data).hexdigest()
def raw(directory,name): return (directory/(name+'.bin')).read_bytes()[2:]


class NativeWaveEvidence(unittest.TestCase):
    def test_hashes_and_exact_compiled_fixture_identity(self):
        for directory in (A,R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                checksum,name=line.split()
                self.assertEqual(digest((directory/name).read_bytes()),checksum,name)
        program=(A/'NWAVE.BIN').read_bytes(); clock=(A/'NCLOCK.BIN').read_bytes()
        self.assertEqual((len(program),sum(int.from_bytes(program[n:n+2],'little') for n in (10,12))),(2221,3422))
        self.assertEqual(program,pack_o65((A/'xwave_native.o65').read_bytes(),0x1000))
        for suffix in ('d64','d81'):
            directory=R/('vice-'+suffix)
            report=json.loads((directory/'result.json').read_text())
            disk=(A/('udeks.'+suffix)).read_bytes()
            fixture=add_apps(disk,[('NWAVE.BIN',program),('NCLOCK.BIN',clock)])
            self.assertEqual(report['disk_sha256'],digest(disk))
            self.assertEqual(report['program_sha256'],digest(program))
            self.assertEqual(report['fixture_sha256'],digest(fixture))
            self.assertEqual((directory/('native-wave.'+suffix)).read_bytes(),fixture)

    def test_grid_samples_every_edge_relocation_and_no_recomputation(self):
        program=(A/'NWAVE.BIN').read_bytes()
        for suffix in ('d64','d81'):
            directory=R/('vice-'+suffix); report=json.loads((directory/'result.json').read_text())
            for key in ('move_without_present','resize_without_worker','stacking_without_worker',
                        'retained_oracle','four_apps','reload','console_live','stack_guards','console_reentry_guard'):
                self.assertTrue(report[key])
            checks={row['check']:row for row in report['records'] if 'check' in row}
            for tag,row in checks.items():
                expected,edges=wave_paths(row['width'],row['height'])
                self.assertEqual(row['edges'],524); self.assertEqual(len(edges),524)
                for kind in ('paths','retained'): self.assertEqual(raw(directory,tag+'-'+kind),expected)
                self.assertEqual(raw(directory,tag+'-samples'),expected_surface())
                self.assertEqual(raw(directory,tag+'-code'),relocate_executable(program,0x2300,0x1200)[16:])
            self.assertEqual(checks['initial-wave']['presents'],checks['moved-wave']['presents'])
            self.assertEqual(checks['restored-wave']['presents'],checks['after-stacking']['presents'])
            def counter(tag): return int.from_bytes(raw(directory,tag)[12:14],'little')
            plotted=counter('engine-plotted')
            self.assertEqual((plotted-counter('engine-before'))&65535,21)
            for tag in ('engine-moved','engine-resized','engine-stacked'):
                self.assertEqual(counter(tag),plotted)
            self.assertEqual((counter('engine-reloaded')-counter('engine-before-reload'))&65535,21)
            self.assertEqual(checks['reloaded-wave']['presents'],1)
            for tag in ('native-wave','native-clock-wave','four-apps'):
                self.assertEqual(raw(directory,tag+'-shadow'),raw(directory,tag+'-bitmap'))

    def test_overlay_only_retires_uploaded_glyphs_and_keeps_console_guard(self):
        assets=(A/'udeks-vdc-text.bin').read_bytes()
        text=(A/'udeks-8502.map').read_text(); segments=map_segments(text)
        self.assertEqual(segments,map_segments((A/'udeks-8502-panic-probe.map').read_text()))
        glyph_overlay_layout(segments); glyph_overlay_entrypoints(segments,map_exports(text))
        paths=(A/'retained-paths.bin').read_bytes()
        self.assertEqual(len(paths),1008)
        self.assertEqual(paths,(A/'retained-paths-panic.bin').read_bytes())
        for suffix in ('d64','d81'):
            directory=R/('vice-'+suffix)
            self.assertEqual(raw(directory,'assets-before'),assets)
            after=raw(directory,'assets-after')
            self.assertEqual(after[:16],assets[:16]); self.assertEqual(after[1024:],assets[1024:])
            # Mutable parser/client state is separate from immutable code.
            offset=segments['GRAPHICSPATHS'][0]-0x96b8
            self.assertEqual(after[16+offset:1024],paths[offset:])
            for tag in ('font-before','font-after','font-reloaded'):
                self.assertEqual(raw(directory,tag),assets[16:1024])
            transcript=(directory/'console-guard.txt').read_text()
            self.assertIn('step 4',transcript)
            self.assertIn('RTS            - A:00 X:00',transcript)

    def test_old_clock_and_all_default_apps_use_the_same_new_kernel(self):
        directory=R/'clock-vice-d71'; report=json.loads((directory/'result.json').read_text())
        self.assertEqual(report['disk_sha256'],digest((A/'udeks.d71').read_bytes()))
        for key in ('resize','drag','targeted_ctrl_c','four_app_compatibility','stack_guards','running_panel'):
            self.assertTrue(report[key])
        for row in report['records']:
            if 'check' not in row: continue
            expected=clock_commands(row['hour'],row['minute'],row['width'],row['height'])
            self.assertEqual(raw(directory,row['check']+'-retained'),expected)
        defaults=json.loads((R/'default-four-apps.json').read_text())
        self.assertEqual(defaults['disk_sha256'],digest((A/'udeks.d64').read_bytes()))
        self.assertTrue(defaults['four_apps'])
