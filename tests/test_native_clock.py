# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from native_clock_probe import clock_commands
from build_graphical_example import check_capacity


class ClockFace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        lib=Path(cls.tmp.name)/'clock.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-I',str(ROOT/'user/include'),str(ROOT/'user/lib/clock_face.c'),
            '-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib))
        cls.lib.udeks_clock_face.argtypes=[ctypes.c_ubyte,ctypes.c_ubyte,
                                          ctypes.c_uint,ctypes.c_ubyte,
                                          ctypes.POINTER(ctypes.c_ubyte)]
        cls.lib.udeks_clock_face.restype=ctypes.c_ubyte

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def face(self,hour,minute,width=72,height=88):
        buf=(ctypes.c_ubyte*(43*8+2))(*([0xa5]*(43*8+2)))
        ptr=ctypes.cast(ctypes.byref(buf,1),ctypes.POINTER(ctypes.c_ubyte))
        count=self.lib.udeks_clock_face(hour,minute,width,height,ptr)
        self.assertEqual(buf[0],0xa5)
        self.assertEqual(buf[-1],0xa5)
        return count,bytes(buf)[1:-1]

    def test_all_minutes_fit_and_use_only_public_retained_primitives(self):
        for hour in range(24):
            for minute in range(60):
                count,commands=self.face(hour,minute)
                self.assertEqual(count,43)
                self.assertEqual(commands,clock_commands(hour,minute))
                for offset in range(0,len(commands),8):
                    cmd=commands[offset:offset+8]
                    self.assertLess(cmd[1],72)
                    self.assertGreaterEqual(cmd[2],12)
                    self.assertLess(cmd[2],88)
                    if offset<38*8:
                        self.assertEqual(cmd[0],1)
                        self.assertLess(cmd[3],72)
                        self.assertTrue(12<=cmd[4]<88)
                        self.assertEqual(cmd[5:],bytes(3))
                    else:
                        self.assertEqual(cmd[0],2)
                        self.assertTrue(all(row<=7 for row in cmd[3:]))

    def test_hands_cardinal_directions_and_hour_fraction(self):
        for hour,minute,hour_end,minute_end in (
            (0,0,(36,28),(36,22)), (3,0,(48,40),(36,22)),
            (6,30,(34,51),(36,58)), (9,45,(25,37),(18,40)),
            (12,15,(37,28),(54,40))):
            _,cmd=self.face(hour,minute)
            self.assertEqual(tuple(cmd[36*8+3:36*8+5]),hour_end)
            self.assertEqual(tuple(cmd[37*8+3:37*8+5]),minute_end)

    def test_face_is_closed_and_digital_uses_24_hour_time(self):
        _,cmd=self.face(23,59)
        for i in range(24):
            self.assertEqual(cmd[i*8+3:i*8+5],cmd[((i+1)%24)*8+1:((i+1)%24)*8+3])
        expected=((7,1,7,4,7),(7,1,7,1,7),(0,2,0,2,0),(7,4,7,1,7),(7,5,7,1,7))
        for i,glyph in enumerate(expected):
            self.assertEqual(tuple(cmd[(38+i)*8+3:(39+i)*8]),glyph)

    def test_invalid_time_is_rejected_without_touching_output(self):
        for hour,minute in ((24,0),(255,0),(0,60),(0,255)):
            count,cmd=self.face(hour,minute)
            self.assertEqual(count,0)
            self.assertEqual(cmd,bytes([0xa5])*(43*8))

    def test_scaled_geometry_matches_oracle_and_stays_inside_client(self):
        for width in (48,49,72,104,160,255,256,280,320):
            for height in (48,49,88,120,170,200):
                for hour,minute in ((0,0),(3,15),(6,30),(9,45),(23,59)):
                    count,cmd=self.face(hour,minute,width,height)
                    self.assertEqual(count,43)
                    self.assertEqual(cmd,clock_commands(hour,minute,width,height))
                    for offset in range(0,38*8,8):
                        self.assertTrue(3<=cmd[offset+1]<width-3)
                        self.assertTrue(15<=cmd[offset+2]<height-3)
                        self.assertTrue(3<=cmd[offset+3]<width-3)
                        self.assertTrue(15<=cmd[offset+4]<height-3)
        self.assertNotEqual(self.face(3,15)[1],self.face(3,15,160,140)[1])

    def test_invalid_geometry_is_rejected_atomically(self):
        for width,height in ((0,88),(47,88),(321,88),(65535,88),(72,0),(72,47),(72,201)):
            count,cmd=self.face(3,15,width,height)
            self.assertEqual(count,0)
            self.assertEqual(cmd,bytes([0xa5])*(43*8))


class GraphicalBuilder(unittest.TestCase):
    def test_capacity_checks_file_and_bss_independently(self):
        image=bytearray(200)
        image[10:12]=(180).to_bytes(2,'little')
        image[12:14]=(50).to_bytes(2,'little')
        check_capacity(image,230)
        for capacity in (0,-1,199,229,65536):
            with self.assertRaises(ValueError): check_capacity(image,capacity)
        image[12:14]=bytes(2)
        with self.assertRaises(ValueError): check_capacity(image,199)

    def test_rejects_invalid_names_and_duplicate_translation_units_before_build(self):
        for options in (['--name','../BAD'], ['--name','TOOLONGTOOLONG'],
                        ['--source','foo/x.c','--source','bar/x.c'],
                        ['--source','entry.c'], ['--export','invalid symbol']):
            result=subprocess.run(['python3',str(ROOT/'tools/build_graphical_example.py'),
                                   *options],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertNotIn('Traceback',result.stderr)

    def test_native_harness_rejects_disk_drive_geometry_mismatch(self):
        for suffix,drive in (('d81','1571'),('d64','1581'),('d71','1581')):
            result=subprocess.run(['python3',str(ROOT/'tools/1986_storage_smoke_build.py'),
                '--emulator','../1986','--roms','../1986/roms',
                '--disk','test.'+suffix,'--drive',drive],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn('use --drive 1581 with D81',result.stderr)


if __name__=='__main__': unittest.main()
