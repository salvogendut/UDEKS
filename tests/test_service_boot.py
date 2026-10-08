# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_d71 as d71
import build_d81 as d81
from build_window_cache import FROZEN_RANGES, layout_maps
from gen_disk_loader_bindings import render
from service_boot_probe import damage_module
from service_image import TIME_BASE, TIME_LIMIT


class ServiceDiskTests(unittest.TestCase):
    def boot_disk(self):
        return bytearray(d71.build_image(b'CBM\0\x1c\0\xd4'+bytes(25),b'',b'',b''))

    def full_side_one(self):
        image = self.boot_disk()
        for track in range(1,36):
            if track != 18:
                for sector in range(d71.sectors_per_track(track)):
                    d71.mark_used(image,track,sector)
        return image

    def test_full_d71_uses_second_bam_and_preserves_exact_file(self):
        original = self.full_side_one()
        data = bytes(range(256))*3
        image = d71.add_data_files(original,[('TIME.SVC',data)],70)
        entry = next(d81.entries(image,d71.sector_offset,18,1))
        self.assertEqual((entry[0],entry[1]),(0x81,36))
        self.assertEqual(d81.file_bytes(image,entry,d71.sector_offset),data)
        bam = d71.sector_offset(18,0)
        self.assertEqual(image[bam+0xdd],d71.sectors_per_track(36)-4)
        for s in range(4):
            self.assertFalse(d71.sector_is_free(image,36,s))
            self.assertTrue(d71.sector_is_free(original,36,s))
        repacked = d81.build_image(image)
        entry = next(d81.entries(repacked,d81.sector_offset,40,3))
        self.assertEqual(d81.file_bytes(repacked,entry,d81.sector_offset),data)
        with self.assertRaisesRegex(ValueError,'second-side'):
            d71.d64_compatibility_image(image)

    def test_default_d64_allocation_never_spills_to_second_side(self):
        image = self.full_side_one()
        before = bytes(image)
        with self.assertRaisesRegex(ValueError,'side one'):
            d71.add_data_files(image,[('TIME.SVC',b'x')])
        self.assertEqual(bytes(image),before)

    def test_bad_and_colliding_names_rejected_without_mutation(self):
        image = d71.add_data_files(d71.blank_d71(),[('TIME.SVC',b'a')])
        for name in ('time.svc','A/B','*','@BAD','A'*17,'','é'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                d71.add_data_files(image,[(name,b'b')])
        self.assertEqual(d81.file_bytes(image,next(d81.entries(image,d71.sector_offset,18,1)),d71.sector_offset),b'a')

    def test_bad_disk_fixture_changes_only_name_or_first_module_byte(self):
        image = d71.add_data_files(self.boot_disk(),[('TIME.SVC',b'USVM'+bytes(706))])
        for suffix,original in (('.d71',image),('.d64',d71.d64_compatibility_image(image)),('.d81',d81.build_image(image))):
            corrupted = damage_module(original,suffix,'corrupt')
            self.assertEqual(sum(a!=b for a,b in zip(original,corrupted)),1)
            absent = damage_module(original,suffix,'missing')
            offset,track,sector = (d81.sector_offset,40,3) if suffix=='.d81' else (d71.sector_offset,18,1)
            entry = next(d81.entries(absent,offset,track,sector))
            self.assertEqual(entry[3:19].rstrip(b'\xa0'),b'KEEP.SVC')
            self.assertEqual(d81.file_bytes(absent,entry,offset),b'USVM'+bytes(706))

    def test_disk_time_cannot_reuse_a_normal_worktree(self):
        result = subprocess.run(['make','-n','DISK_TIME=1','boot'],cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('DISK_TIME is isolated',result.stderr)


class ServiceBindingsTests(unittest.TestCase):
    def test_module_private_binding_is_required_only_for_candidate(self):
        symbols = {'_udeks_lifecycle_slots_private':(0xc100,'RLA'),
                   '_udeks_lifecycle_current_private':(0xc200,'RLA'),
                   '_udeks_bootfs_finish_error':(0xf400,'REA')}
        with patch('gen_disk_loader_bindings.map_exports',return_value=symbols):
            self.assertNotIn('TIME_MODULE_REQUEST',render('map'))
            with self.assertRaises(KeyError): render('map','candidate')
        for addr,kind in ((0x2006,'RLA'),(0x93cf,'RLA'),(0x93d0,'RLA'),(0x4000,'RLZ')):
            symbols['_udeks_time_slot_request']=(addr,kind)
            with patch('gen_disk_loader_bindings.map_exports',return_value=symbols):
                if kind=='RLA' and addr<TIME_BASE:
                    self.assertIn(f'TIME_MODULE_REQUEST = ${addr:04x}',render('map','candidate'))
                else:
                    with self.assertRaises(ValueError): render('map','candidate')

    def test_cache_guard_accepts_only_bounded_service_overlay(self):
        segments = {name:(low,high,high-low+1) for name,(low,high) in FROZEN_RANGES.items()}
        segments.update(CODE=(0x2006,0x8000,0x5ffb),RODATA=(0x8001,0x8100,0x100),
            DATA=(0x8101,0x8103,3),BSS=(0x8104,TIME_BASE-1,TIME_BASE-0x8104),
            VDCASSETS=(TIME_LIMIT,0x9aff,1112),PATHSTATE=(0x96b8,0x96bf,8),
            GRAPHICSPATHS=(0x96c0,0x9700,65),GRAPHICSCODE=(0xc00,0xc0f,16),
            GRAPHICSHELP=(0xa100,0xa10f,16),SERVICEBOOT=(TIME_BASE,TIME_BASE+517,518))
        with patch('build_window_cache.map_segments',return_value=segments):
            self.assertEqual(layout_maps('normal','panic'),segments)
        for bounds in ((TIME_BASE-1,TIME_BASE+517,519),(TIME_BASE,TIME_LIMIT,729),
                       (TIME_BASE,TIME_BASE+517,517)):
            with patch('build_window_cache.map_segments',return_value=dict(segments,SERVICEBOOT=bounds)):
                with self.assertRaises(ValueError): layout_maps('normal','panic')


if __name__ == '__main__':
    unittest.main()
