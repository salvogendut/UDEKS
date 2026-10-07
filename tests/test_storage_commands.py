# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class Command:
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        path=Path(cls.tmp.name)/'command.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-D__fastcall__=','-I'+str(ROOT/'user/include'),
            str(ROOT/('user/bin/'+cls.name+'.c')),str(ROOT/'user/lib/error_string.c'),
            str(ROOT/('tests/fixtures/'+cls.name+'_client.c')),'-o',str(path)],check=True)
        cls.lib=c.CDLL(str(path))
        cls.lib.udeks_program_main.argtypes=[c.c_uint8,c.POINTER(c.c_char_p)]
        cls.lib.udeks_program_main.restype=c.c_uint8
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self): self.lib.test_reset()
    def value(self,name): return c.c_uint8.in_dll(self.lib,'test_'+name)
    def invoke(self,*args):
        return self.lib.udeks_program_main(len(args),(c.c_char_p*(len(args)+1))(
            *(a.encode() for a in args),None))
    def output(self): return (c.c_char*256).in_dll(self.lib,'test_message').value


class Save(Command,unittest.TestCase):
    name='save'
    def test_exact_binary_lengths_and_exclusive_mode(self):
        for size in (0,1,24,254,255,515,4096):
            self.setUp()
            self.assertEqual(self.invoke('save','/file',str(size)),0)
            self.assertEqual(c.c_uint.in_dll(self.lib,'test_size').value,size)
            self.assertEqual(bytes((c.c_uint8*4096).in_dll(self.lib,'test_data'))[:size],
                             bytes(i&255 for i in range(size)))
            self.assertEqual(bytes((c.c_uint8*4).in_dll(self.lib,'test_modes'))[:2],b'\3\0')
            self.assertEqual(self.value('closes').value,2)
    def test_default_and_check_only(self):
        self.assertEqual(self.invoke('save','/file'),0)
        self.assertEqual(c.c_uint.in_dll(self.lib,'test_size').value,515)
        self.value('opens').value=self.value('writes').value=0
        self.assertEqual(self.invoke('save','-c','/file'),0)
        self.assertEqual(self.value('writes').value,0)
        self.assertEqual((c.c_uint8*4).in_dll(self.lib,'test_modes')[0],0)
    def test_invalid_arguments_do_not_open(self):
        for args in (('save',),('save','/file','-1'),('save','/file','4097'),
                     ('save','/file','65536'),('save','/file',''),('save','/file','12x'),
                     ('save','-c'),('save','/file','24','extra')):
            self.setUp()
            self.assertEqual(self.invoke(*args),1)
            self.assertEqual(self.value('opens').value,0)
    def test_short_write_never_retries_and_closes(self):
        self.value('short').value=1
        self.assertEqual(self.invoke('save','/file'),1)
        self.assertEqual(self.value('writes').value,1)
        self.assertEqual(self.value('closes').value,1)
        self.assertIn(b'Input/output error',self.output())
    def test_write_failure_survives_successful_close(self):
        self.value('error').value=28
        self.assertEqual(self.invoke('save','/file'),1)
        self.assertEqual(self.value('writes').value,1)
        self.assertEqual(self.value('closes').value,1)
        self.assertIn(b'No space left',self.output())
    def test_close_failure_is_fatal_even_for_empty_file(self):
        self.value('close_error').value=5
        self.assertEqual(self.invoke('save','/file','0'),1)
        self.assertEqual(self.value('opens').value,1)
        self.assertEqual(self.value('closes').value,1)
    def test_corrupt_readback_is_rejected_and_closed(self):
        self.value('corrupt').value=1
        self.assertEqual(self.invoke('save','/file'),1)
        self.assertEqual(self.value('closes').value,2)
        self.assertEqual(self.value('fd').value,2)


class MountRW(Command,unittest.TestCase):
    name='mount_rw'
    def test_explicit_modes_and_default_read_only(self):
        for option,flags in (('ro',0),('rw',1),('remount,ro',2),('remount,rw',3)):
            self.setUp()
            self.assertEqual(self.invoke('mount','-o',option,'8','/'),0)
            self.assertEqual([self.value(n).value for n in ('device','op','flags','length')],[8,17,flags,1])
        self.assertEqual(self.invoke('mount','9','/mnt'),0)
        self.assertEqual(self.value('flags').value,0)
        self.assertEqual(self.value('length').value,4)
        self.assertEqual(self.invoke('/bin/umount','/mnt'),0)
        self.assertEqual(self.value('op').value,18)
    def test_invalid_options_never_submit(self):
        for args in (('mount','-o','rw,ro','8','/'),('mount','-o','rw'),
                     ('mount','-o','remount','8','/'),('mount','08','/'),
                     ('mount','7','/'),('mount','8','/etc'),('umount','-o','rw','/mnt')):
            self.setUp()
            self.assertEqual(self.invoke(*args),1)
            self.assertEqual(self.value('calls').value,0)
    def test_service_error_is_meaningful_and_nonzero(self):
        for error,phrase in ((16,b'busy'),(30,b'Read-only'),(19,b'No such device')):
            self.setUp(); self.value('error').value=error
            self.assertEqual(self.invoke('mount','-o','remount,rw','8','/'),1)
            self.assertIn(phrase,self.output())
            self.assertEqual(self.value('fd').value,2)


if __name__=='__main__': unittest.main()
