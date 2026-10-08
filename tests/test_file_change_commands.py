# SPDX-License-Identifier: GPL-3.0-or-later
"""Three standalone commands: argc/argv, stderr and no implicit retry/force."""
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FileChangeCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.libs = {}
        for name in ('cp','mv','rm'):
            path = Path(cls.temp.name) / (name+'.so')
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
                            '-I'+str(ROOT/'include'), '-I'+str(ROOT/'user/include'),
                            str(ROOT/f'user/bin/{name}.c'), str(ROOT/'user/lib/error_string.c'),
                            str(ROOT/'tests/fixtures/file_change_command.c'), '-o', str(path)], check=True)
            lib = cls.libs[name] = c.CDLL(str(path))
            lib.udeks_program_main.argtypes = [c.c_uint8, c.POINTER(c.c_char_p)]
            lib.udeks_program_main.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def run_command(self, name, args, errno=0):
        lib = self.libs[name]
        for symbol in ('test_calls','test_operation','test_bad_descriptor'):
            c.c_uint8.in_dll(lib,symbol).value=0
        for symbol, size in (('test_source',64),('test_destination',64),('test_output',256)):
            (c.c_uint8*size).in_dll(lib,symbol)[:] = bytes(size)
        c.c_uint8.in_dll(lib,'udeks_errno').value=errno
        c.c_uint8.in_dll(lib,'test_result').value=255 if errno else 0
        argv = (c.c_char_p*(len(args)+2))(name.encode(), *args, None)
        status = lib.udeks_program_main(len(args)+1, argv)
        self.assertEqual(c.c_uint8.in_dll(lib,'test_bad_descriptor').value,0)
        output=bytes((c.c_uint8*256).in_dll(lib,'test_output')).split(b'\0')[0]
        return status, output, c.c_uint8.in_dll(lib,'test_calls').value

    def test_valid_commands_are_silent_and_forward_exact_paths_once(self):
        for name, op in (('cp',26),('mv',25),('rm',27)):
            args=[b'/mnt/Mixed Case'] if name=='rm' else [b'/hello',b'../other']
            self.assertEqual(self.run_command(name,args),(0,b'',1))
            self.assertEqual(c.c_uint8.in_dll(self.libs[name],'test_operation').value,op)
            self.assertEqual(bytes((c.c_uint8*64).in_dll(self.libs[name],'test_source')).split(b'\0')[0],args[0])
            if name!='rm':
                self.assertEqual(bytes((c.c_uint8*64).in_dll(self.libs[name],'test_destination')).split(b'\0')[0],args[1])

    def test_usage_rejects_missing_extra_empty_and_unsupported_flags(self):
        for name in self.libs:
            for args in ([],[b'-r',b'file'],[b'-f',b'a',b'b'],[b'a',b'b',b'c'],[b'']):
                status, text, calls = self.run_command(name,args)
                self.assertEqual((status,calls),(1,0),(name,args))
                self.assertTrue(text.startswith(name.encode()+b' [--] '))
            if name!='rm':
                for args in ([b'a'],[b'a',b''],[b'a',b'-target']):
                    self.assertEqual(self.run_command(name,args)[2],0)

    def test_double_dash_allows_literal_dash_names(self):
        for name in self.libs:
            args=[b'--',b'-source']+([] if name=='rm' else [b'-target'])
            self.assertEqual(self.run_command(name,args),(0,b'',1))

    def test_errors_are_meaningful_and_never_retried(self):
        for name in self.libs:
            args=[b'file']+([] if name=='rm' else [b'target'])
            for errno, message in ((2,b'No such file or directory'),(17,b'File exists'),
                                    (18,b'Invalid cross-device link'),(22,b'Invalid argument'),
                                    (30,b'Read-only filesystem'),(5,b'Input/output error')):
                self.assertEqual(self.run_command(name,args,errno),
                                 (1,name.encode()+b': '+message+b'\n',1))


if __name__ == '__main__': unittest.main()
