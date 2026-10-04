# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BankedGraphics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        target = Path(cls.temp.name)/'graphics.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
            '-Wno-unknown-pragmas', '-shared', '-fPIC', '-D__fastcall__=',
            '-I'+str(ROOT/'include'), str(ROOT/'tests/fixtures/banked_graphics.c'),
            '-o', str(target)], check=True)
        cls.lib = c.CDLL(str(target))

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.lib.test_reset()
        self.r = (c.c_ubyte*38).in_dll(self.lib, 'graphics_request')
        self.memory = (c.c_ubyte*65536).in_dll(self.lib, 'graphics_memory')
        self.owners = (c.c_ubyte*5).in_dll(self.lib, 'test_owner')

    def scalar(self, name, value=None, kind=c.c_ubyte):
        obj = kind.in_dll(self.lib, 'test_'+name)
        if value is not None: obj.value = value
        return obj.value

    def request(self, payload, **fields):
        self.r[:] = b'UTRQ\0\x09\x01\x17\x2a\0\x18'+bytes(27)
        self.r[14:14+len(payload)] = bytes(payload)
        for offset, value in fields.items(): self.r[int(offset)] = value
        self.lib.udeks_banked_graphics_request()
        self.assertEqual(self.r[8], 42)  # original sequence preserved
        self.assertEqual(self.r[6], 0x80 if self.r[12] else 2)
        return self.r[12]

    def create(self, task=3):
        self.scalar('task', task); self.lib.test_admit(task-3)
        self.assertEqual(self.request([1,108,0,30,104,133,0x16]+list(b'XCALC\0\0\0')), 0)
        return self.r[11]

    def present(self, handle, pointer=0x2300, count=1):
        return self.request([2,handle,pointer&255,pointer>>8,count])

    def test_envelope_caller_and_fixed_window_flags(self):
        self.assertEqual(self.request([1], **{'5':8}), 38)
        self.assertEqual(self.request([1]), 22)  # unregistered task
        self.lib.test_admit(0)
        for offset,value in ((9,1),(13,1),(10,23)):
            self.assertEqual(self.request([1], **{str(offset):value}), 22)
        for task in (0,1,2,5,255):
            self.scalar('task', task)
            self.assertEqual(self.request([1]), 22)
        self.scalar('task',3)
        for flags in (0,8,0x18,0x96):
            self.assertEqual(self.request([1,10,0,10,104,133,flags]),22)

    def test_cannot_draw_close_or_consume_input_for_another_owner(self):
        a=self.create(); b=self.create(4)
        self.lib.test_click(a,20,40)
        self.assertEqual(self.request([3,a]),22)
        self.assertEqual(self.request([4,a]),22)
        self.assertEqual(self.present(a,0x3500),22)
        self.assertEqual(self.owners[a],0x83)
        self.scalar('task',3)
        self.assertEqual(self.request([3,a]),0)
        self.assertEqual(bytes(self.r[14:18]),b'\x03\x14\0\x28')
        self.assertEqual(self.request([3,a]),0)
        self.assertEqual(self.r[14],1)
        self.assertEqual(self.owners[b],0x84)

    def test_desktop_is_lazy_and_create_failure_is_retryable(self):
        self.assertEqual(self.lib.udeks_banked_graphics_exec(b'console'),0)
        self.assertEqual(self.scalar('init_calls'),0)
        self.assertEqual(self.request([1]),22)
        self.assertEqual(self.scalar('init_calls'),0)
        payload=[1,108,0,30,104,133,0x16]+list(b'HELLO\0\0\0')
        self.scalar('init_error',1)
        self.assertEqual(self.request(payload),5)
        self.assertEqual(self.scalar('active'),0)
        self.assertEqual(bytes(self.owners),bytes(5))
        self.scalar('init_error',0)
        self.assertEqual(self.request(payload),0)
        self.assertEqual(self.scalar('init_calls'),2)
        self.create(4)
        self.assertEqual(self.scalar('init_calls'),2)  # never clear a live desktop

    def test_present_rejects_bad_ranges_without_writes(self):
        h=self.create()
        for pointer,count in ((0x22ff,1),(0x3500,0),(0x34f9,1),(0xfffe,1),(0x2300,49)):
            self.assertEqual(self.present(h,pointer,count),22)
        self.assertEqual(self.scalar('writes',kind=c.c_uint),0)
        self.assertEqual(self.scalar('repaints',kind=c.c_uint),0)

    def test_entire_candidate_validated_before_commit(self):
        h=self.create()
        self.memory[0x2300:0x2308]=bytes((1,5,17,10,20,0,0,0))
        self.assertEqual(self.present(h),0)
        original=bytes(self.memory[0xcd00:0xce80])
        self.memory[0x2308:0x2310]=bytes((99,0,0,0,0,0,0,0))
        self.assertEqual(self.present(h,count=2),22)
        self.assertEqual(bytes(self.memory[0xcd00:0xce80]),original)
        self.assertEqual(self.scalar('writes',kind=c.c_uint),1)
        self.memory[0x2308:0x2310]=bytes((0,1,2,3,4,1,0,0))
        self.assertEqual(self.present(h,count=2),22)
        self.assertEqual(bytes(self.memory[0xcd00:0xce80]),original)

    def test_repaint_uses_retained_image_at_current_geometry(self):
        h=self.create()
        self.memory[0x2300:0x2308]=bytes((1,5,17,10,20,0,0,0))
        self.assertEqual(self.present(h),0)
        self.memory[0x2300:0x2308]=bytes(8)  # client may now reuse its buffer
        self.lib.test_move(h,40,50)
        self.assertEqual(self.scalar('x',kind=c.c_uint),45)
        self.assertEqual(self.scalar('y',kind=c.c_uint),67)
        self.assertEqual(self.scalar('draws',kind=c.c_uint),2)

    def test_close_and_zombie_cleanup_do_not_retire_live_peer(self):
        a=self.create(); b=self.create(4)
        self.scalar('task',3)
        self.assertEqual(self.request([4,a]),0)
        self.assertEqual(self.request([3,a]),0)
        self.assertEqual(self.r[14],0)
        self.assertEqual(self.owners[b],0x84)
        self.lib.udeks_banked_graphics_poll()
        self.assertEqual(self.owners[b],0x84)
        (c.c_ubyte*2).in_dll(self.lib,'test_state')[1]=6
        self.scalar('reap_busy',16)
        self.lib.udeks_banked_graphics_poll()
        self.assertEqual(self.owners[b],0)
        self.scalar('task',4)
        self.assertEqual(self.request([3,b]),0)  # closing until reap permitted
        self.scalar('reap_busy',0)
        self.lib.udeks_banked_graphics_poll()
        self.assertEqual(self.request([3,b]),22)

    def test_second_client_has_its_own_retained_allocation(self):
        a=self.create(); self.assertEqual(self.present(a),0)
        before=bytes(self.memory[0xcd00:0xce80])
        b=self.create(4)
        self.memory[0x3500:0x3508]=bytes((1,2,3,4,5,0,0,0))
        self.assertEqual(self.present(b,0x2300),22)
        self.assertEqual(self.present(b,0x3500),0)
        self.assertEqual(bytes(self.memory[0xcd00:0xce80]),before)
        self.assertEqual(bytes(self.memory[0xce80:0xce88]),bytes(self.memory[0x3500:0x3508]))

    def test_indexed_launch_close_wait_and_reuse(self):
        for index,name in ((0,b'xcalc'),(1,b'xdraw')):
            self.assertEqual(self.lib.udeks_banked_graphics_start(index),0)
            self.assertEqual(self.scalar('selector'),index+3)
            self.assertEqual(bytes((c.c_ubyte*17).in_dll(self.lib,'test_path')),
                             bytes((5,))+name+bytes(11))
            self.assertEqual(self.lib.udeks_banked_graphics_running(index),1)
            self.assertEqual(self.lib.udeks_banked_graphics_start(index),4)
        self.assertEqual(self.lib.udeks_banked_graphics_stop(1),0)
        self.assertEqual(self.lib.udeks_banked_graphics_running(1),0)
        self.assertEqual(self.lib.udeks_banked_graphics_running(0),1)
        self.assertEqual(self.lib.udeks_banked_graphics_start(1),4)  # still live/closing
        (c.c_ubyte*2).in_dll(self.lib,'test_state')[1]=6
        self.lib.udeks_banked_graphics_poll()
        self.assertEqual(self.lib.udeks_banked_graphics_start(1),0)
        self.assertEqual(self.lib.udeks_banked_graphics_start(2),4)
        self.assertEqual(self.lib.udeks_banked_graphics_stop(255),1)
        self.assertEqual(self.lib.udeks_banked_graphics_running(2),0)

    def test_load_errors_preserve_peer_and_do_not_publish_client(self):
        self.assertEqual(self.lib.udeks_banked_graphics_start(0),0)
        for error,result in ((2,3),(16,4),(12,4),(8,5),(5,6)):
            self.scalar('load_error',error)
            self.assertEqual(self.lib.udeks_banked_graphics_start(1),result)
            self.assertEqual(self.lib.udeks_banked_graphics_running(1),0)
            self.assertEqual(self.lib.udeks_banked_graphics_running(0),1)
        self.scalar('load_error',0);self.scalar('activate_error',8)
        self.assertEqual(self.lib.udeks_banked_graphics_start(1),5)
        self.assertEqual(self.lib.udeks_banked_graphics_running(1),0)

    def test_names_unknown_to_service_use_free_slots_and_are_copied(self):
        launch=self.lib.udeks_banked_graphics_exec
        launch.argtypes=[c.c_char_p]
        names=(c.c_ubyte*32).in_dll(self.lib,'udeks_banked_graphics_names')
        for index,name in enumerate((b'orbit',b'canvas_2')):
            source=c.create_string_buffer(name)
            self.assertEqual(launch(source),0)
            source[0]=b'!'
            self.assertEqual(self.scalar('selector'),3+index)
            self.assertEqual(bytes(names[index*16:index*16+16]),name.ljust(16,b'\0'))
        before=bytes(names)
        self.assertEqual(launch(b'third'),4)
        self.assertEqual(bytes(names),before)
        self.assertEqual(launch(b'12345678901234567'),5)
        self.assertEqual(bytes(names),before)
        (c.c_ubyte*2).in_dll(self.lib,'test_state')[0]=6
        self.lib.udeks_banked_graphics_poll()
        self.assertEqual(launch(b'1234567890123456'),0)
        self.assertEqual(bytes(names[:16]),b'1234567890123456')
        self.assertEqual(bytes(names[16:]),before[16:])
