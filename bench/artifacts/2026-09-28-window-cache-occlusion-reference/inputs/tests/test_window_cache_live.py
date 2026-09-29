# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from window_cache_live import NAME, PROOF, bitmap_oracle, validate_live_slot
from graphics_raster_link_audit import segments

ARTIFACT=ROOT / 'bench/artifacts' / NAME
RESULT=ROOT / 'bench/results' / NAME


class WindowCacheLiveTests(unittest.TestCase):
    def test_live_code_allows_only_exact_row_operands_and_four_scratch_bytes(self):
        from window_cache_controller_delivery import fixture
        module=(PROOF / 'build/bench/window-cache-compact/module.bin').read_bytes()
        slot=bytearray(fixture(module))
        for offset in (0x4d,0x74):slot[offset:offset+2]=(0x5bc3).to_bytes(2,'little')
        slot[0xd1:0xd5]=b'\x01\x02\x03\x04'
        validate_live_slot(slot,module,168,104)
        for offset in (0,0x4d,0x74,0xd0,0xd5,0x1009,0x100a,0x1010):
            bad=bytearray(slot);bad[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):
                validate_live_slot(bad,module,168,104)

    def test_oracle_handles_unaligned_right_edge_and_detects_pixel_corruption(self):
        window=bytearray(17);window[:3]=b'\x01\x02\x01'
        window[4:6]=(151).to_bytes(2,'little');window[6]=93
        window[7:9]=(168).to_bytes(2,'little');window[9]=104
        image=bytes((i*37+13)&255 for i in range(2224))
        bitmap=bytearray(8000)
        for y in range(104):
            for x in range(168):
                offset=((y+93)&248)*40+((y+93)&7)+((x+151)&~7)
                if (image[y*21+x//8]>>(7-(x&7)))&1:
                    bitmap[offset]|=1<<(7-((x+151)&7))
        self.assertEqual(bitmap_oracle(bitmap,bitmap,image,window)['pixels'],17472)
        bad=bytearray(bitmap);bad[3751]^=1
        with self.assertRaises(ValueError):bitmap_oracle(bitmap,bad,image,window)
        with self.assertRaises(ValueError):bitmap_oracle(bitmap[:-1],bitmap,image,window)

    def test_actual_links_regenerate_bridges_without_segment_or_runtime_growth(self):
        report=json.loads((ARTIFACT / 'build/report.json').read_text())
        self.assertEqual((report['transport_bytes'],report['remaining_padding']),(377,159))
        private=ARTIFACT / 'inputs/build/window-cache-live/repo'
        for name in ('udeks-8502','udeks-8502-panic-probe'):
            self.assertEqual(segments((private / 'build/8502' / (name+'.map')).read_text()),report['segments'])
        self.assertEqual(report['segments']['VICSHADOW'],{'start':0xa1e0,'end':0xc11f,'size':8000})
        self.assertEqual(report['helpers']['udeks-8502'],report['helpers']['udeks-8502-panic-probe'])
        for key in ('inputs_sha256','source_sha256'):
            for name,sha in report[key].items():
                self.assertEqual(hashlib.sha256((ARTIFACT / 'inputs' / name).read_bytes()).hexdigest(),sha,name)
        for fmt,sha in report['disk_sha256'].items():
            self.assertEqual(hashlib.sha256((ARTIFACT / 'build' / f'udeks-cache.{fmt}').read_bytes()).hexdigest(),sha)

    def test_two_formats_native_moves_pixels_no_replot_and_vice_capture(self):
        report_sha=hashlib.sha256((ARTIFACT / 'build/report.json').read_bytes()).hexdigest()
        for engine in ('1986','vice'):
            binding=json.loads((RESULT / f'{engine}-run.json').read_text())
            self.assertEqual(binding['report_sha256'],report_sha)
            self.assertEqual(set(binding['results']),{'d71','d64'})
            for name,sha in binding['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((RESULT / name).read_bytes()).hexdigest(),sha,name)
            for fmt,values in binding['results'].items():
                self.assertEqual(values['pixels'],17472)
                if engine=='1986':
                    log=(RESULT / f'1986-{fmt}.log').read_text()
                    self.assertEqual(sum(line.startswith('cache move ') for line in log.splitlines()),16)
                    self.assertIn('PASS: live cached moves, full pixels, fallback, cancellation and restart',log)
                    self.assertIn('command: xinit -q -> accepted',log)
                    windows=(RESULT / f'1986-{fmt}-window.bin').read_bytes()
                    window=next(windows[i:i+17] for i in range(0,68,17) if windows[i:i+2]==b'\x01\x02')
                    module=(PROOF / 'build/bench/window-cache-compact/module.bin').read_bytes()
                    validate_live_slot((RESULT / f'1986-{fmt}-slot.bin').read_bytes(),module,168,104)
                else:
                    self.assertGreater(values['coalesced_drains'],0)
                    self.assertEqual(values['pending'],0)
                    window=(RESULT / f'vice-{fmt}-window.bin').read_bytes()
                raw=lambda name:(RESULT / f'{engine}-{fmt}-{name}.bin').read_bytes()
                self.assertEqual(bitmap_oracle(raw('shadow'),raw('bitmap'),raw('image'),window)['pixels'],17472)

    def test_manifests_bind_evidence_and_exclude_rom_snapshots(self):
        for directory in (ARTIFACT,RESULT):
            self.assertFalse(list(directory.rglob('*.vsf')))
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)
