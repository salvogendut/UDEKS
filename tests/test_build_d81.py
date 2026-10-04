# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_d81 as d81
from build_d71 import blank_d71, boot_locations, PAYLOAD_BLOCKS, sector_offset, install_prg_file, mark_used
from add_disk_apps import add_apps, directory_names


class D81(unittest.TestCase):
    def source(self):
        image=blank_d71()
        for index,(t,s) in enumerate(boot_locations(1+PAYLOAD_BLOCKS)):
            pos=sector_offset(t,s)
            image[pos:pos+256]=bytes((index&255,))*256
            mark_used(image,t,s)
        image[:7]=b'CBM\0\x1c\0\xd4'
        for i,data in enumerate((b'',b'X',bytes(range(256))*3)):
            install_prg_file(image,'FILE'+str(i),data,file_type=0x81)
        return image

    def test_standard_geometry_header_bams_and_free_counts(self):
        image=d81.blank_d81()
        self.assertEqual(len(image),819200)
        self.assertEqual(image[d81.sector_offset(40,0):d81.sector_offset(40,0)+4],b'\x28\x03D\0')
        for t in range(1,81):
            pos=d81.bam_entry(t)
            self.assertEqual(image[pos],sum(b.bit_count() for b in image[pos+1:pos+6]))
            self.assertEqual(image[pos],36 if t==40 else 40)
        self.assertEqual(d81.sector_offset(80,39),819200-256)
        for t,s in ((0,0),(81,0),(1,40),(40,-1)):
            with self.assertRaises(ValueError): d81.sector_offset(t,s)

    def test_native_boot_preserves_track_sector_not_linear_offsets(self):
        source=self.source(); before=bytes(source); image=d81.build_image(source)
        self.assertEqual(bytes(source),before)
        for t,s in boot_locations(1+PAYLOAD_BLOCKS):
            self.assertEqual(image[d81.sector_offset(t,s):d81.sector_offset(t,s)+256],
                             source[sector_offset(t,s):sector_offset(t,s)+256])
            self.assertFalse(d81.is_free(image,t,s))
        source_files={e[3:19]:d81.file_bytes(source,e,sector_offset)
                      for e in d81.entries(source,sector_offset,18,1)}
        dest_files={e[3:19]:d81.file_bytes(image,e,d81.sector_offset)
                    for e in d81.entries(image,d81.sector_offset,40,3)}
        self.assertEqual(source_files,dest_files)
        self.assertEqual(d81.build_image(source),image)

    def test_independent_installer_extends_directory_and_preserves_boot(self):
        image=d81.build_image(self.source()); before=bytes(image)
        program=b'UDEX'+bytes(20)
        files=[(f'APP{i}.BIN',program) for i in range(20)]
        result=add_apps(image,files)
        self.assertEqual(image,before)
        self.assertEqual(len(directory_names(result)),23)
        for entry in d81.entries(result,d81.sector_offset,40,3):
            if entry[3:6]==b'APP': self.assertEqual(d81.file_bytes(result,entry,d81.sector_offset),program)
        for t,s in boot_locations(1+PAYLOAD_BLOCKS):
            pos=d81.sector_offset(t,s)
            self.assertEqual(result[pos:pos+256],before[pos:pos+256])
        with self.assertRaises(ValueError): add_apps(result,[('APP0.BIN',program)])

    def test_invalid_input_cyclic_chains_and_full_media(self):
        with self.assertRaises(ValueError): d81.build_image(bytes(349696))
        image=d81.blank_d81(); pos=d81.sector_offset(40,3)
        image[pos:pos+2]=bytes((40,3))
        with self.assertRaises(ValueError): list(d81.entries(image,d81.sector_offset,40,3))
        image=d81.blank_d81()
        for t in range(1,81):
            for s in range(40): d81.mark_used(image,t,s)
        with self.assertRaisesRegex(ValueError,'full'): d81.install_file(image,'X',b'X')


if __name__=='__main__': unittest.main()
