# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Calculator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        library = Path(cls.temp.name)/'calc.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c99', '-Wall', '-Wextra',
                        '-Werror', '-I', str(ROOT/'include'), str(ROOT/'src/apps/calc.c'),
                        '-o', str(library)], check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.value = ctypes.c_long.in_dll(cls.lib, 'udeks_calc_value')
        cls.error = ctypes.c_ubyte.in_dll(cls.lib, 'udeks_calc_error')
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.lib.udeks_calc_reset()
    def keys(self, text):
        for key in text: self.lib.udeks_calc_key(ord(key))
        result = ctypes.create_string_buffer(12)
        self.lib.udeks_calc_format(result)
        return result.value.decode()
    def test_decimal_add_subtract(self):
        self.assertEqual(self.keys('1.25+2.75='), '4.00')
        self.assertEqual(self.keys('-7.25='), '-3.25')
    def test_multiply_divide_and_truncation(self):
        for expression, expected in [('C1.50*2=', '3.00'), ('C7.5/2.5=', '3.00'),
                ('C1/3=', '0.33'), ('C1N/3=', '-0.33'), ('C200000/1=', '200000.00')]:
            self.assertEqual(self.keys(expression), expected)
    def test_sign_and_negative_fraction_entry(self):
        self.assertEqual(self.keys('5+N.25='), '4.75')
        self.assertEqual(self.keys('C.N'), '-0.00')
        self.assertEqual(self.keys('5'), '-0.50')
    def test_chain_replace_operator_and_no_repeat_equals(self):
        self.assertEqual(self.keys('2+3*4=='), '20.00')
        self.assertEqual(self.keys('C2+*3='), '6.00')
    def test_errors_clear_and_new_entry(self):
        self.assertEqual(self.keys('3/0='), 'E1')
        self.assertEqual(self.keys('+N='), 'E1')
        self.assertEqual(self.keys('4'), '4.00')
        self.assertEqual(self.keys('C200000+0.01='), 'E2')
        self.assertEqual(self.keys('C'), '0.00')
    def test_entry_and_intermediate_bounds(self):
        self.assertEqual(self.keys('2000000'), 'E2')
        self.assertEqual(self.keys('C200000*2='), 'E2')
        self.assertEqual(self.keys('C1000*100='), '100000.00')
        self.assertEqual(self.keys('C1.2399'), '1.23')
    def test_unsupported_keys_do_not_mutate(self):
        self.keys('12.34')
        self.assertEqual(self.keys('xyz '), '12.34')
