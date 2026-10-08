# SPDX-License-Identifier: GPL-3.0-or-later
"""Private exact-name backend; does not substitute for service preflight."""
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CbmMutate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        output = Path(cls.tmp.name) / 'mutate.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-DUDEKS_IEC_WRITE', '-DUDEKS_IEC_MUTATE',
                        '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/filesystem/cbm_mutate.c'),
                        str(ROOT/'tests/fixtures/mutate_transport.c'), '-o', str(output)], check=True)
        cls.lib = c.CDLL(str(output))
        cls.lib.udeks_cbm_mutate.argtypes = [c.c_uint8, c.c_uint8, c.c_char_p, c.c_char_p]
        cls.lib.udeks_cbm_mutate.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def setUp(self):
        self.lib.test_reset()
        self.calls = (c.c_uint16*7).in_dll(self.lib, 'test_calls')
        self.buffer = (c.c_uint8*38).in_dll(self.lib, 'udeks_iec_filename')
        self.reply()

    def byte(self, name): return c.c_uint8.in_dll(self.lib, name)
    def reply(self, text=b'00, OK,00,00\r', *, eoi=True):
        values = list(text)
        if eoi and values: values[-1] |= 256
        data = (c.c_uint16*80).in_dll(self.lib, 'test_status')
        data[:len(values)] = values
        c.c_uint16.in_dll(self.lib, 'test_size').value = len(values)

    def call(self, op=1, source=b'OLD', dest=b'NEW', unit=8):
        pad = lambda s: s.ljust(16, b'\xa0') if s is not None else None
        return self.lib.udeks_cbm_mutate(unit, op, pad(source), pad(dest))

    def command(self): return bytes(self.buffer[:self.byte('udeks_iec_filename_length').value])

    def test_exact_rename_copy_and_scratch_commands(self):
        for op, expected, status in ((1,b'R0:NEW=OLD',b'00, OK,00,00\r'),
                                     (2,b'C0:NEW=0:OLD',b'00, OK,00,00\r'),
                                     (3,b'S0:OLD',b'01,FILES SCRATCHED,01,00\r')):
            self.setUp(); self.reply(status)
            self.assertEqual(self.call(op, dest=None if op==3 else b'NEW'), 0)
            self.assertEqual(self.command(), expected)
            self.assertEqual(list(self.calls[:3]), [1,1,1])
            self.assertEqual(list(self.calls[4:]), [1,1,0])

    def test_maximum_names_and_case_are_preserved_without_buffer_overrun(self):
        source=b'abcdefghijklmnop'; dest=b'1234567890ABCDEF'
        self.assertEqual(self.call(2,source,dest,11),0)
        self.assertEqual(self.command(),b'C0:'+dest+b'=0:'+source)
        self.assertEqual(len(self.command()),38)
        self.assertEqual(self.byte('test_device').value,11)
        self.assertEqual(self.call(1,b'\xc1',b'A'),0)
        self.assertEqual(self.command(),b'R0:A=\xc1')

    def test_invalid_inputs_never_touch_transport_or_shared_buffer(self):
        for name in (None,b'',b'.',b'..',b' A',b'A ',b'@A',b'A*',b'A?',b'A/B',
                     b'A,B',b'A:B',b'A=B',b'A\0B',b'A\xa0B',b'A\rB',b'\xff'):
            self.assertEqual(self.call(source=name),22,name)
            self.assertEqual(self.call(dest=name),22,name)
        for op in (0,4,255): self.assertEqual(self.call(op),22)
        for unit in (0,7,12,255): self.assertEqual(self.call(unit=unit),22)
        self.assertEqual(self.call(3),22)  # extraneous destination
        self.assertEqual(list(self.calls),[0]*7)
        self.assertEqual(bytes(self.buffer),b'Z'*38)
        self.assertEqual(self.byte('udeks_iec_filename_length').value,0x5a)

    def test_same_exact_name_and_busy_begin_preserve_transport(self):
        self.assertEqual(self.call(dest=b'OLD'),17)
        self.assertEqual(list(self.calls),[0]*7)
        self.byte('test_begin_error').value=4
        self.assertEqual(self.call(),16)
        self.assertEqual(list(self.calls),[1,0,0,0,0,0,0])
        self.assertEqual(bytes(self.buffer),b'Z'*38)

    def test_scratch_requires_one_file_not_generic_success(self):
        for code,count,expected in ((1,0,2),(1,1,0),(1,2,5),(1,99,5),(0,0,5)):
            self.setUp(); self.reply(f'{code:02},FILES SCRATCHED,{count:02},00\r'.encode())
            self.assertEqual(self.call(3,dest=None),expected)
            self.assertEqual(self.calls[1],1)  # never retry
        self.reply(b'01,FILES SCRATCHED,01,00\r')
        for op in (1,2): self.assertEqual(self.call(op),5)

    def test_full_error_status_maps_to_specific_errno(self):
        for code,expected in ((26,30),(60,16),(62,2),(63,17),(70,16),(72,28),(74,19),(23,5)):
            for track, sector in ((0,0), (40,3)):
                self.setUp(); self.reply(f'{code:02},ERROR,{track:02},{sector:02}\r'.encode())
                self.assertEqual(self.call(),expected)
                self.assertEqual(self.calls[5],1)

    def test_malformed_or_incomplete_status_is_not_success(self):
        for text in (b'',b'00,\r',b'0,OK,00,00\r',b'00,,00,00\r',b'00,OK,0,00\r',
                     b'00,OK,00,0\r',b'00,OK,00,00',b'00,OK,00,01\r',b'00,OK,01,00\r',
                     b'0X,OK,00,00\r',b'00,'+b'A'*70+b',00,00\r'):
            self.setUp(); self.reply(text)
            self.assertEqual(self.call(),5,text)
            self.assertEqual(list(self.calls[4:6]),[1,1])
        self.reply(eoi=False)
        self.assertEqual(self.call(),5)

    def test_transport_errors_cleanup_once_without_retry(self):
        for field in ('test_command_error','test_status_error','test_untalk_error'):
            self.setUp(); self.byte(field).value=2
            self.assertEqual(self.call(),5)
            self.assertEqual(self.calls[1],1)
            self.assertEqual(self.calls[5],1)
            if field=='test_command_error':
                self.assertEqual(self.calls[2],0)
                self.assertEqual(self.calls[6],1)


if __name__=='__main__': unittest.main()
