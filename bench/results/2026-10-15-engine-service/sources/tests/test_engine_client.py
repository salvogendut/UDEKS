# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class EngineClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();so=Path(cls.tmp.name)/'client.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-Iinclude','-Iuser/include',
            'user/examples/engine/client.c','tests/fixtures/engine_client.c','-o',str(so)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(so));cls.lib.udeks_program_main.argtypes=[c.c_uint8,c.POINTER(c.c_char_p)];cls.lib.udeks_program_main.restype=c.c_uint8
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_original_error_exit_survives_successful_error_output(self):
        for error in (2,9,11,28,38,71):
            for args in ((b'engtest',),(b'engtest',b'--nop'),(b'engtest',b'--stop')):
                c.c_uint8.in_dll(self.lib,'engine_cli_test_error').value=error
                self.assertEqual(self.lib.udeks_program_main(len(args),(c.c_char_p*len(args))(*args)),error)
                self.assertEqual(c.c_uint8.in_dll(self.lib,'engine_client_error').value,error)
                self.assertEqual(c.c_uint8.in_dll(self.lib,'udeks_errno').value,0)
