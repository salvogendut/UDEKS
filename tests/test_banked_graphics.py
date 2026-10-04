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
            '-I'+str(ROOT/'include'), '-I'+str(ROOT/'user/include'),
            str(ROOT/'tests/fixtures/banked_graphics.c'),str(ROOT/'user/lib/wave_paths.c'),
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

    def test_resize_requires_new_minor_and_exactly_one_sizing_policy(self):
        self.lib.test_admit(0)
        payload=[1,10,0,10,72,88,0x0e]+list(b'CLOCK\0\0\0')
        self.assertEqual(self.request(payload),22)
        for flags in (0,6,0x18,0x1e,0x8e,0x0f):
            payload[6]=flags
            self.assertEqual(self.request(payload,**{'5':10}),22)
        payload[6]=0x0e
        self.assertEqual(self.request(payload,**{'5':10}),0)
        self.assertEqual((c.c_ubyte*5).in_dll(self.lib,'test_flags')[self.r[11]],0x0e)

    def geometry(self,handle,width,height):
        return self.request([3,handle,width&255,width>>8,height],**{'5':10})

    def test_geometry_is_owned_coalesced_and_does_not_consume_pending_click(self):
        a=self.create();b=self.create(4)
        self.lib.test_resize(a,280,170);self.lib.test_click(a,25,33)
        self.assertEqual(self.geometry(a,104,133),22)
        self.scalar('task',3)
        for _ in range(2):
            self.assertEqual(self.geometry(a,104,133),0)
            self.assertEqual(self.r[11],7)
            self.assertEqual(self.r[14],2)
            self.assertEqual(bytes(self.r[18:21]),bytes((24,1,170)))
        self.assertEqual(self.geometry(a,280,170),0)
        self.assertEqual(bytes(self.r[14:21]),bytes((3,25,0,33,24,1,170)))
        self.assertEqual(self.geometry(a,280,170),0)
        self.assertEqual(self.r[14],1)
        self.lib.test_move(a,10,20)
        self.assertEqual(self.geometry(a,280,170),0)
        self.assertEqual(self.r[14],1) # pure move does not ask the app to redraw
        self.lib.test_resize(a,90,100);self.lib.test_resize(a,120,150)
        self.assertEqual(self.geometry(a,280,170),0)
        self.assertEqual(bytes(self.r[18:21]),bytes((120,0,150)))
        self.scalar('task',4)
        self.assertEqual(self.geometry(b,104,133),0)
        self.assertEqual(self.r[14],1) # peer never resized

    def test_old_events_and_closed_new_events_keep_their_contract(self):
        a=self.create();self.lib.test_resize(a,140,150)
        self.lib.test_click(a,5,20)
        self.assertEqual(self.request([3,a]),0)
        self.assertEqual(self.r[11],4)
        self.assertEqual(bytes(self.r[14:18]),bytes((3,5,0,20)))
        self.assertEqual(self.request([4,a]),0)
        self.assertEqual(self.geometry(a,104,133),0)
        self.assertEqual(self.r[11],7)
        self.assertEqual(self.r[14],0)
        self.assertEqual(self.request([3,a]),0)
        self.assertEqual(self.r[11],4)
        self.assertEqual(self.r[14],0)

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
        original=bytes(self.memory[0xc600:0xcb00])
        self.memory[0x2308:0x2310]=bytes((99,0,0,0,0,0,0,0))
        self.assertEqual(self.present(h,count=2),22)
        self.assertEqual(bytes(self.memory[0xc600:0xcb00]),original)
        self.assertEqual(self.scalar('writes',kind=c.c_uint),1)
        self.memory[0x2308:0x2310]=bytes((0,1,2,3,4,1,0,0))
        self.assertEqual(self.present(h,count=2),22)
        self.assertEqual(bytes(self.memory[0xc600:0xcb00]),original)

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
        before=bytes(self.memory[0xc600:0xcb00])
        b=self.create(4)
        self.memory[0x3500:0x3508]=bytes((1,2,3,4,5,0,0,0))
        self.assertEqual(self.present(b,0x2300),22)
        self.assertEqual(self.present(b,0x3500),0)
        self.assertEqual(bytes(self.memory[0xc600:0xcb00]),before)
        self.assertEqual(bytes(self.memory[0xcb00:0xcb08]),bytes(self.memory[0x3500:0x3508]))

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

    def paths(self,handle,data,pointer=0x2300,minor=12):
        self.memory[pointer:pointer+len(data)]=data
        return self.request([5,handle,pointer&255,pointer>>8,len(data)&255,len(data)>>8],**{'5':minor})

    def test_paths_validate_before_commit_and_use_independent_retained_slots(self):
        a=self.create(); first=bytes((2,10,20,5,250,0,0,0))
        self.assertEqual(self.paths(a,first),0)
        self.assertEqual(bytes(self.memory[0xc600:0xc608]),first)
        self.assertEqual((c.c_uint*2).in_dll(self.lib,'udeks_retained_lengths')[0],0x8008)
        b=self.create(4)
        self.assertEqual(self.paths(b,first,0x3500),0)
        before=bytes(self.memory[0xc600:0xd000])
        lengths=bytes((c.c_uint*2).in_dll(self.lib,'udeks_retained_lengths'))
        writes=self.scalar('writes',kind=c.c_uint)
        repaints=self.scalar('repaints',kind=c.c_uint)
        malformed=(b'',bytes(7),bytes(1288),bytes(16), # counts / excessive pad
            bytes((1,0,0,0,0,0,0,0)), bytes((128,0,0,0,0,0,0,0)),
            bytes((2,0,0,255,0,0,0,0)), # negative x
            bytes((2,0,0,0,255,0,0,0)), # negative y
            bytes((130,63,0,1,0,0,0,0)), # x 319 -> 320
            bytes((2,0,199,0,1,0,0,0)), # y 199 -> 200
            bytes((130,64,1,0,0,0,0,0)), # initial x outside display
            bytes((2,0,200,0,0,0,0,0)), # initial y outside display
            bytes((2,0,0,1,1,0,0,1)), # nonzero trailing padding
            bytes((4,0,0,1,1,1,1,1))) # truncated delta / no terminator
        for data in malformed:
            with self.subTest(data=data[:8]):
                self.assertEqual(self.paths(b,data,0x3500),22)
                self.assertEqual(bytes(self.memory[0xc600:0xd000]),before)
                self.assertEqual(bytes((c.c_uint*2).in_dll(self.lib,'udeks_retained_lengths')),lengths)
        self.assertEqual(self.scalar('writes',kind=c.c_uint),writes)
        self.assertEqual(self.scalar('repaints',kind=c.c_uint),repaints)

    def test_paths_owner_range_version_and_format_switch(self):
        a=self.create(); data=bytes((2,10,20,5,250,0,0,0))
        self.assertEqual(self.paths(a,data,minor=11),38)
        for pointer in (0x22ff,0x34f9,0x3500,0xfff8):
            self.assertEqual(self.paths(a,data,pointer),22)
        self.assertEqual(self.paths(a,data,0x34f8),0) # exact allocation end
        b=self.create(4)
        self.assertEqual(self.paths(a,data,0x3500),22) # wrong owner
        self.assertEqual(self.paths(b,data,0x3ff8),0)
        self.memory[0x3500:0x3508]=bytes((1,5,17,10,20,0,0,0))
        self.assertEqual(self.present(b,0x3500),0)
        self.assertEqual((c.c_uint*2).in_dll(self.lib,'udeks_retained_lengths')[1],8)
        self.assertEqual(self.present(b,0x3500,0),0)
        self.assertEqual((c.c_uint*2).in_dll(self.lib,'udeks_retained_lengths')[1],0)

    def test_paths_multiblock_and_nine_bit_coordinates_repaint_without_client(self):
        h=self.create()
        data=bytes((131,44,100,250,1,6,255,2,1,2,10,10,0,0,0,0))
        self.assertEqual(self.paths(h,data),0)
        expected=((400,120,394,121),(394,121,400,120),(101,22,111,32))
        lines=(c.c_int*4*2048).in_dll(self.lib,'test_lines')
        self.assertEqual(tuple(tuple(line) for line in lines[:3]),expected)
        self.memory[0x2300:0x2310]=bytes(16)
        self.lib.test_move(h,40,50)
        self.assertEqual(tuple(tuple(line) for line in lines[3:6]),
            tuple((x-60,y+30,x2-60,y2+30) for x,y,x2,y2 in expected))
        self.assertEqual(self.scalar('writes',kind=c.c_uint),2)

    def test_maximum_paths_image_and_late_error_are_atomic(self):
        h=self.create()
        # Five 127-point paths (255 bytes each) + terminator and four pad bytes.
        data=(bytes((127,10,20))+bytes(252))*5+bytes(5)
        self.assertEqual(len(data),1280)
        self.assertEqual(self.paths(h,data),0)
        self.assertEqual(self.scalar('draws',kind=c.c_uint),630)
        before=bytes(self.memory[0xc600:0xd000])
        self.assertEqual(self.paths(h,data[:-1]+b'\1'),22)
        self.assertEqual(bytes(self.memory[0xc600:0xd000]),before)
        self.assertEqual(self.scalar('draws',kind=c.c_uint),630)

    def test_module_install_preserves_launch_name_and_never_replays_delivery(self):
        blob=bytes(i%251 for i in range(1008))
        self.memory[0xcc00:0xcff0]=blob
        self.assertEqual(self.lib.udeks_banked_graphics_exec(b'stream_plotter'),0)
        self.assertEqual(bytes((c.c_ubyte*1008).in_dll(self.lib,'graphics_overlay')),blob)
        self.assertEqual(bytes((c.c_ubyte*17).in_dll(self.lib,'test_path')),b'\x0estream_plotter\0\0')
        self.memory[0xcc00:0xcff0]=bytes(1008) # now a retained image, not delivery
        self.assertEqual(self.lib.udeks_banked_graphics_exec(b'peer'),0)
        self.assertEqual(bytes((c.c_ubyte*1008).in_dll(self.lib,'graphics_overlay')),blob)

    def test_full_wave_stream_decodes_to_exactly_the_original_grid_edges(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from native_wave_probe import wave_paths
        from native_worker_probe import expected_surface
        self.lib.udeks_wave_paths.argtypes=[c.POINTER(c.c_byte),c.c_uint,c.c_ubyte,c.POINTER(c.c_ubyte)]
        self.lib.udeks_wave_paths.restype=c.c_uint
        h=self.create()
        lines=(c.c_int*4*2048).in_dll(self.lib,'test_lines')
        for width,height in ((48,48),(176,112),(320,200)):
            buf=(c.c_ubyte*1128)(); samples=(c.c_byte*525).from_buffer_copy(expected_surface())
            self.assertEqual(self.lib.udeks_wave_paths(samples,width,height,buf),1128)
            oracle,edges=wave_paths(width,height)
            self.assertEqual(bytes(buf),oracle)
            self.scalar('draws',0,kind=c.c_uint)
            self.assertEqual(self.paths(h,bytes(buf)),0)
            self.assertEqual(self.scalar('draws',kind=c.c_uint),524)
            self.assertEqual([tuple(line) for line in lines[:524]],
                             [(x+100,y+20,xx+100,yy+20) for x,y,xx,yy in edges])

    def test_static_locals_are_not_emitted_at_executable_entry_labels(self):
        source=(ROOT/'src/services/window/retained_paths.c').read_text()
        self.assertIn('#pragma bss-name("PATHSTATE")',source)
        self.assertNotIn('#pragma bss-name("GRAPHICSPATHS")',source)
        for path in ('cfg/8502-bootstrap.cfg','cfg/8502-panic-probe.cfg'):
            config=(ROOT/path).read_text()
            self.assertIn('PATHSTATE: load = PATHS, type = ro;',config)
            self.assertIn('GRAPHICSPATHS: load = PATHS, type = ro;',config)
