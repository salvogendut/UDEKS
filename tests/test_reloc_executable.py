# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from o65_to_udex import pack_o65, relocate_executable


def o65(text, data=b'', bss=0, text_reloc=b'\0', data_reloc=b'\0', options=b''):
    header=struct.pack('<9H',0x1000,len(text),0x1000+len(text),len(data),
        0x1000+len(text)+len(data),bss,2,26,0)
    return b'\x01\0o65\0\0\x08'+header+options+b'\0'+text+data+b'\0\0'+text_reloc+data_reloc+b'\0\0'


class RelocExecutable(unittest.TestCase):
    def test_word_split_low_high_bss_and_absolute_references(self):
        # Word TEXT; split LOW/HIGH DATA; literal address lookalike and ABS;
        # DATA has a word BSS pointer. Only compiler-labelled fields change.
        stream=o65(b'\x08\x10\x09\x10\x34\x12\x16\xff',b'\x0a\x10',bss=4,
            text_reloc=b'\x01\x82\x02\x23\x01\x43\x09\x03\x81\0',
            data_reloc=b'\x01\x84\0')
        executable=pack_o65(stream,0x1000)
        for base in (0x200,0x2300,0x3500):
            fixed=relocate_executable(executable,base,0xb00)
            hi=base>>8
            self.assertEqual(fixed[16:],bytes((8,hi,9,hi,0x34,0x12,0x16,0xff,10,hi)))
            self.assertEqual(int.from_bytes(fixed[14:16],'little'),base)
            self.assertEqual(int.from_bytes(fixed[12:14],'little'),4)

    def test_zp_and_absolute_references_stay_fixed(self):
        data=o65(b'\x02\0\x03\0\x16\xff',text_reloc=b'\x01\x85\x02\x45\x03\x02\x81\0')
        self.assertEqual(relocate_executable(pack_o65(data,0x1000),0x3500,0xb00)[16:],b'\x02\0\x03\0\x16\xff')

    def test_offset_escape_and_non_base_entry(self):
        source=b'\xea'*300+b'\x01\x10'
        executable=pack_o65(o65(source,text_reloc=b'\xff\x2f\x82\0'),0x1002)
        relocated=relocate_executable(executable,0x2300,0xb00)
        self.assertEqual(relocated[-2:],b'\x01\x23')
        self.assertEqual(relocated[14:16],b'\x02\x23')

    def test_o65_options_do_not_make_executable_nondeterministic(self):
        plain=o65(b'\x60')
        timestamp=o65(b'\x60',options=b'\x06\x04TIME')
        self.assertEqual(pack_o65(plain,0x1000),pack_o65(timestamp,0x1000))

    def test_rejects_unsupported_headers_and_noncontiguous_segments(self):
        original=o65(b'\xea\x60',b'\0',bss=2)
        for offset,value in ((0,0),(5,1),(7,0x48),(8,1),(12,0),(16,0),(20,3),(22,31),(24,1)):
            bad=bytearray(original);bad[offset]=value
            with self.subTest(offset=offset), self.assertRaises(ValueError): pack_o65(bad,0x1000)
        for entry in (0xfff,0x1003):
            with self.assertRaises(ValueError): pack_o65(original,entry)

    def test_rejects_truncated_imported_exported_or_trailing_streams(self):
        original=o65(b'\x60')
        for end in range(len(original)):
            with self.subTest(end=end), self.assertRaises(ValueError): pack_o65(original[:end],0x1000)
        for offset in (28,len(original)-2):
            bad=bytearray(original);bad[offset]=1
            with self.assertRaises(ValueError): pack_o65(bad,0x1000)
        with self.assertRaises(ValueError): pack_o65(original+b'\0',0x1000)
        with self.assertRaises(ValueError): pack_o65(o65(b'\x60',options=b'\x01'),0x1000)

    def test_rejects_invalid_relocation_descriptors_bounds_and_overlap(self):
        for table in (b'\x01\x80\0',b'\x01\xc2\0',b'\x01\x8a\0',b'\x01\x86\0',
                      b'\x03\x82\0',b'\x02\x82\0',b'\xff\0',
                      b'\x01\x82\x01\x42\0\0'):
            with self.subTest(table=table), self.assertRaises(ValueError):
                pack_o65(o65(b'\x10\x10',text_reloc=table),0x1000)

    def test_reference_rejects_bad_tables_before_any_mutation(self):
        executable=pack_o65(o65(b'\x10\x10\x12\x10',text_reloc=b'\x01\x82\x02\x82\0'),0x1000)
        for offset,value in ((5,1),(7,2),(8,1),(9,0),(14,4),(20,255),(22,4),(24,1)):
            bad=bytearray(executable);bad[offset]=value
            before=bytes(bad)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                relocate_executable(bad,0x3500,0xb00)
            self.assertEqual(bytes(bad),before)
        for bad in (executable[:-1],executable+b'\0'):
            with self.assertRaises(ValueError): relocate_executable(bad,0x3500,0xb00)

    def test_staging_allocation_and_page_alignment_are_independent_bounds(self):
        plain=pack_o65(o65(b'\x60',bss=0xaff),0x1000)
        relocate_executable(plain,0x3500,0xb00)
        for base,capacity in ((0x3501,0xb00),(0x3500,0xaff),(0xff00,0xb00),(0,0x1000)):
            with self.assertRaises(ValueError): relocate_executable(plain,base,capacity)
        # Image+BSS can fit while header/table staging does not.
        plain=pack_o65(o65(b'\xea'*100),0x1000)
        with self.assertRaises(ValueError): relocate_executable(plain,0x3500,100)
