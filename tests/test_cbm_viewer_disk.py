# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from add_cbm_viewer import add_viewer
from build_d71 import blank_d71, install_prg_file, sector_is_free, sectors_per_track, d64_compatibility_image, mark_used as d71_mark_used
from build_d81 import blank_d81, mark_used, SIZE
from png_to_cbm import build
from storage_public_probe import files


class ViewerDisk(unittest.TestCase):
    app=b'UDEX\0\x02\x01\0\0\x10\x01\0\0\0\0\x10\x60\0\0'
    picture=build(b'\xa0',8,1)

    def test_all_formats_are_private_copies_with_exact_files_and_untouched_boot(self):
        for disk in (blank_d71(),blank_d81(),d64_compatibility_image(blank_d71())):
            disk=bytearray(disk)
            # Empty media has no boot loader. Model the real boot reservation.
            (mark_used if len(disk)==SIZE else d71_mark_used)(disk,1,0)
            before=bytes(disk)
            result=add_viewer(disk,self.app,[('demo.cbm',self.picture)])
            self.assertEqual(bytes(disk),before)
            self.assertEqual(result[:256],before[:256])
            self.assertEqual(files(result),{b'XVIEW.BIN':self.app,b'DEMO.CBM':self.picture})

    def test_d71_uses_second_side_when_first_is_full(self):
        disk=blank_d71()
        free=sum(sector_is_free(disk,t,s) for t in range(1,36) if t!=18 for s in range(sectors_per_track(t)))
        data=b'A'*(free*254)
        install_prg_file(disk,'FULL',data,file_type=0x81)
        before=bytes(disk)
        result=add_viewer(disk,self.app,[('demo.cbm',self.picture)])
        self.assertEqual(bytes(disk),before)
        self.assertEqual(files(result),{b'FULL':data,b'XVIEW.BIN':self.app,b'DEMO.CBM':self.picture})
        with self.assertRaises(ValueError): add_viewer(d64_compatibility_image(disk),self.app,[('demo.cbm',self.picture)])

    def test_invalid_names_content_and_collisions_never_change_source(self):
        disk=blank_d71(); before=bytes(disk)
        for pics in ([('a.cbm',b'broken')],[('../a.cbm',self.picture)],
                     [('a.cbm',self.picture),('A.CBM',self.picture)]):
            with self.assertRaises(ValueError): add_viewer(disk,self.app,pics)
            self.assertEqual(bytes(disk),before)
