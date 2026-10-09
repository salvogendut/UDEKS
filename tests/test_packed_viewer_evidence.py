# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind the streaming viewer, demo disks and live pixel captures together."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from native_app_layout import fitting_allocations, check_coexistence
from png_to_cbm import parse
from storage_public_probe import files

A=ROOT/'bench/results/2026-10-09-packed-viewer'


def digest(data):return hashlib.sha256(data).hexdigest()


class PackedViewerEvidence(unittest.TestCase):
    def test_manifest_covers_every_preserved_artifact(self):
        named=set()
        for line in (A/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1)
            self.assertNotIn(name,named);named.add(name)
            self.assertEqual(digest((A/name).read_bytes()),expected,name)
        self.assertEqual(named,{str(p.relative_to(A)) for p in A.rglob('*')
                               if p.is_file() and p.name!='SHA256SUMS'})

    def test_private_image_has_no_full_bitmap_and_fits_ordinary_slots(self):
        app=(A/'XVIEW.BIN').read_bytes()
        self.assertEqual((len(app),int.from_bytes(app[10:12],'little'),int.from_bytes(app[12:14],'little')),
                         (3217,2455,64))
        self.assertEqual(fitting_allocations(app),[3,5])
        disk=files((A/'demo/udeks-packed.d81').read_bytes())
        self.assertEqual(check_coexistence({'viewer':[3,5],
            'clock':fitting_allocations(disk[b'XCLOCK.BIN']),
            'wave':fitting_allocations(disk[b'XWAVE.BIN'])}),6)
        self.assertEqual(check_coexistence({'first':[3,5],'second':[3,5]}),2)

    def test_demo_disks_preserve_base_files_and_use_the_qualified_service(self):
        manifest=json.loads((A/'demo/manifest.json').read_text())
        service=json.loads((ROOT/'bench/results/2026-10-09-bitmap-integration/report.json').read_text())
        self.assertEqual(manifest['abi_minor'],20)
        self.assertEqual(manifest['app_sha256'],digest((A/'XVIEW.BIN').read_bytes()))
        for fmt in ('d71','d81'):
            image=(A/f'demo/udeks-packed.{fmt}').read_bytes();directory=files(image)
            record=manifest['disks'][fmt]
            self.assertEqual(digest(image),record['sha256'])
            self.assertEqual(record['base_sha256'],service['disk_sha256'][fmt])
            self.assertEqual(directory[b'XVIEW.BIN'],(A/'XVIEW.BIN').read_bytes())
            for name,sha in record['original_files'].items():
                self.assertEqual(digest(directory[name.encode()]),sha,name)
            for name,sha in manifest['pictures'].items():
                self.assertEqual(directory[name.encode()],(A/'demo'/name).read_bytes())
                self.assertEqual(digest(directory[name.encode()]),sha)

    def test_reports_bind_both_vice_disks_and_native_1986(self):
        for fmt in ('d71','d81'):
            report=json.loads((A/f'vice-{fmt}/report.json').read_text())
            self.assertEqual(report['source_sha256'],digest((A/f'demo/udeks-packed.{fmt}').read_bytes()))
            self.assertEqual(report['app_sha256'],digest((A/'XVIEW.BIN').read_bytes()))
            self.assertEqual(report['checks'][-1],dict(check='pending-close-cancel-stream-reuse-and-guards',passed=True))
        native=json.loads((A/'1986/report.json').read_text())
        self.assertEqual(native['exit_status'],0)
        self.assertEqual(native['emulator_tracked_changes'],'')
        self.assertEqual(native['disk_sha256'],digest((A/'demo/udeks-packed.d81').read_bytes()))
        self.assertEqual(native['app_sha256'],digest((A/'XVIEW.BIN').read_bytes()))
        self.assertIn('PASS packed xview:',(A/'1986/run.log').read_text())

    def pixels(self,bitmap,name,x,y):
        width,height,rows=parse((A/'demo'/name).read_bytes())
        self.assertEqual(len(bitmap),8000)
        for yy in range(height):
            for xx in range(width):
                at=((y+yy)//8)*320+((x+xx)//8)*8+(y+yy)%8
                self.assertEqual(bool(bitmap[at]&(128>>((x+xx)%8))),bool(rows[yy][xx]),(name,xx,yy))

    def test_vice_pixels_match_cbm_sources_after_load_drag_uncover_and_cancel(self):
        for fmt in ('d71','d81'):
            for tag,name,x,y in (
                ('initial','ALEX128.CBM',24,18),('oom-peer-intact','ALEX128.CBM',24,18),
                ('dragged','ALEX128.CBM',54,48),('uncovered','ALEX128.CBM',54,48),
                ('wide-picture','CLOCK160.CBM',24,18),('two-pictures','ALEX128.CBM',184,18),
                ('second-picture','CLOCKWORK.CBM',24,18),
                ('background-survives-ctrl-c','ALEX128.CBM',184,18)):
                with self.subTest(disk=fmt,tag=tag):
                    base=A/f'vice-{fmt}'
                    bitmap=(base/f'{tag}-bitmap.bin').read_bytes()
                    shadow=(base/f'{tag}-shadow.bin').read_bytes()
                    self.assertEqual((bitmap[:2],shadow[:2]),(b'\0\x60',b'\xe0\xa1'))
                    self.assertEqual(bitmap[2:],shadow[2:]);self.pixels(bitmap[2:],name,x,y)

    def test_native_mouse_pixels_match_same_cbm_sources(self):
        for tag,name,x,y in (('initial','ALEX128.CBM',24,18),('dragged','ALEX128.CBM',54,48),
                            ('uncovered','ALEX128.CBM',54,48),('CLOCK160','CLOCK160.CBM',24,18),
                            ('pair','ALEX128.CBM',184,18),('second','CLOCKWORK.CBM',24,18),
                            ('survivor','ALEX128.CBM',184,18),('small-uncovered','ALEX2.CBM',24,18)):
            with self.subTest(tag=tag):self.pixels((A/f'1986/{tag}.bin').read_bytes(),name,x,y)


if __name__=='__main__':unittest.main()
