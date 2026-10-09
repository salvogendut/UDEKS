# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from reu_graphics_layout import layout, seal, install


class HiddenGraphicsLayout(unittest.TestCase):
    def setUp(self):
        self.segments={'BITMAPCODE':(0xd000,0xdc9d,3230),
            'BITMAPSTATE':(0xdc9e,0xdd0f,114),'BITMAPID':(0xdff0,0xdfff,16)}
        self.image=bytes([0x60])*3230+bytes(4080-3230)+b'RBMP\0\1'+bytes(10)
        self.payload=b'\0\x12'+bytes(0xe900-0x1200)
    def test_sealed_delivery_is_exact_and_bounded(self):
        blob=seal(self.image,self.segments);out=install(self.payload,blob)
        first=2+0x7300-0x1200
        self.assertEqual(len(out),len(self.payload))
        self.assertEqual(out[first:first+4096],blob)
        self.assertEqual(out[:first],self.payload[:first])
        self.assertEqual(out[first+4096:],self.payload[first+4096:])
        self.assertEqual(int.from_bytes(blob[-10:-8],'little'),sum(blob[:-16])&65535)
    def test_layout_missing_noncontiguous_and_overrun_rejected(self):
        for name,value in (('BITMAPCODE',(0xd001,0xdc9e,3230)),
                ('BITMAPSTATE',(0xdca0,0xdd11,114)),
                ('BITMAPSTATE',(0xdc9e,0xdff0,851)),
                ('BITMAPID',(0xdfe0,0xdfef,16))):
            with self.subTest(name=name,value=value):
                bad=dict(self.segments);bad[name]=value
                with self.assertRaises(ValueError):layout(bad)
        with self.assertRaises(ValueError):layout({})
    def test_bad_bss_padding_trailer_checksum_or_source_collision_rejected(self):
        for at in (3230,4079,4095):
            bad=bytearray(self.image);bad[at]=1
            with self.assertRaises(ValueError):seal(bad,self.segments)
        blob=seal(self.image,self.segments)
        for at in (0,4080,4086,4095):
            bad=bytearray(blob);bad[at]^=1
            with self.assertRaises(ValueError):install(self.payload,bad)
        for at in (2+0x7300-0x1200,2+0x82ff-0x1200):
            bad=bytearray(self.payload);bad[at]=1
            with self.assertRaises(ValueError):install(bad,blob)
        with self.assertRaises(ValueError):install(self.payload[:-1],blob)
    def test_task_page_clears_skip_cpu_ports(self):
        for filename,label in (('src/scheduler/task_context.s','clear_task_pages:'),
                ('src/scheduler/task_yield_handler.s','spawn_clear_pages:')):
            source=(ROOT/filename).read_text()
            self.assertIn('ldy #$02\n        lda #$00\n'+label,source)
    def test_runtime_banks_and_bounded_buffer(self):
        source=(ROOT/'src/services/window/reu_runtime.s').read_text()
        self.assertIn('RUN = $f400',source)
        self.assertIn('lda $7300,y',source);self.assertIn('sta $d000,y',source)
        self.assertIn('jmp _udeks_vic_buffer_restore',source)
        self.assertIn('sta $4180,y',source);self.assertIn('lda $4180,y',source)
        # The runtime transport never replaces the VIC/cache gateway owner.
        self.assertNotIn('$f68a',source)
        self.assertIn('sta error\n        cmp #0',source)
