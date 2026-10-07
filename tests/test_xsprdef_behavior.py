# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute the actual C editor, not a nicer reimplementation of its algorithm."""
import ctypes as c
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SpriteEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        target = Path(cls.temp.name)/'editor.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                        '-Wno-pointer-to-int-cast', '-shared', '-fPIC',
                        '-D__fastcall__=', '-I'+str(ROOT/'include'),
                        str(ROOT/'tests/fixtures/xsprdef.c'), '-o', str(target)], check=True)
        cls.lib = c.CDLL(str(target))
        for name in ('pixels', 'bank', 'commands'):
            getattr(cls.lib, 'editor_'+name).restype = c.POINTER(c.c_ubyte)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self): self.lib.editor_reset()

    def select(self, slot=0):
        self.assertEqual(self.lib.editor_click(30+slot*26+19, 99), 1)
        self.assertEqual(self.lib.editor_selected(), slot)

    def render(self):
        count = self.lib.editor_draw()
        self.assertLessEqual(count, 56)
        commands = bytes(self.lib.editor_commands()[:count*8])
        canvas = bytearray([7])*(248*192)
        def fill(x,y,w,h,color):
            for yy in range(max(14,y),min(189,y+h)):
                for xx in range(max(3,x),min(245,x+w)):
                    canvas[yy*248+xx] = color
        for offset in range(0,len(commands),8):
            op,x,y,a,b,color,d,e = cmd = commands[offset:offset+8]
            if op == 0: fill(x,y,a,b,color)
            elif op == 2 or 3 <= op <= 10:
                scale = 2 if op == 2 else op-2
                width = 3 if op == 2 else 8
                for row,data in enumerate(cmd[3:]):
                    for bit in range(width):
                        if data & (1 << (width-1-bit)):
                            fill(x+bit*scale,y+row*scale,scale,scale,0)
            else: self.fail(('unexpected command',cmd))
        return canvas

    def test_every_pattern_fits_and_both_views_are_pixel_exact(self):
        self.select()
        rng = random.Random(41)
        patterns = [bytes(63), bytes([255])*63,
                    bytes((0x55 if y%2 else 0xaa) for y in range(21) for _ in range(3)),
                    bytes([0x81])*63]
        patterns += [bytes(rng.randrange(256) for _ in range(63)) for _ in range(20)]
        for sprite in patterns:
            c.memmove(self.lib.editor_pixels(),sprite,63)
            image = self.render()
            for y in range(21):
                for x in range(24):
                    color = 0 if sprite[y*3+x//8] & (128>>(x%8)) else 7
                    self.assertEqual(image[(20+y)*248+208+x],color,(x,y,'preview'))
                    for yy in range(8):
                        row=(20+y*8+yy)*248+8+x*8
                        self.assertEqual(image[row:row+8],bytes([color])*8,(x,y,'editor'))

    def test_every_pixel_including_last_row_and_column_is_editable(self):
        self.select()
        for y in range(21):
            for x in range(24):
                self.assertEqual(self.lib.editor_click(8+x*8+7,20+y*8+7),1)
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),bytes([255])*63)
        for x,y in ((7,20),(200,20),(8,19),(8,188)):
            self.assertEqual(self.lib.editor_click(x,y),0)

    def test_list_hitboxes_match_the_complete_visible_buttons(self):
        for slot in range(8):
            bx=30+slot*26
            for x,y in ((bx,80),(bx+19,99)):
                self.lib.editor_reset()
                self.assertEqual(self.lib.editor_click(x,y),1)
                self.assertEqual(self.lib.editor_selected(),slot)
            for x,y in ((bx-1,80),(bx+20,80),(bx,79),(bx,100)):
                self.lib.editor_reset()
                self.assertEqual(self.lib.editor_click(x,y),0)
                self.assertEqual(self.lib.editor_mode(),0)

    def test_save_confirmation_cancel_discard_and_slot_isolation(self):
        self.select(7)
        self.lib.editor_click(199,187)
        edited=bytes(self.lib.editor_pixels()[:63])
        self.lib.editor_click(231,76)  # S, bottom-right of visible button
        self.assertEqual(self.lib.editor_confirming(),1)
        self.assertEqual(self.lib.editor_click(8,20),0)  # freeze edit during prompt
        image=self.render()
        self.assertEqual(image[52*248+208],0)  # S remains visibly framed
        self.assertEqual(image[78*248+208],0)  # B remains visibly framed
        self.lib.editor_click(231,102)  # B cancels prompt, not the edit
        self.assertEqual(self.lib.editor_mode(),1)
        self.assertEqual(self.lib.editor_confirming(),0)
        self.assertEqual(bytes(self.lib.editor_bank()[:504]),bytes(504))
        self.lib.editor_click(208,52);self.lib.editor_click(208,52)
        self.assertEqual(self.lib.editor_mode(),0)
        self.assertEqual(bytes(self.lib.editor_bank()[:441]),bytes(441))
        self.assertEqual(bytes(self.lib.editor_bank()[441:504]),edited)
        self.select(7);self.lib.editor_click(8,20)
        self.lib.editor_click(208,78)  # discard working changes
        self.select(7)
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),edited)

    def test_clear_invert_and_confirmation_button_gaps(self):
        self.select()
        self.lib.editor_click(231,154)  # I
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),bytes([255])*63)
        self.lib.editor_click(231,128)  # C
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),bytes(63))
        self.lib.editor_click(208,52)
        for x,y in ((208,104),(208,130),(208,77),(232,52)):
            self.assertEqual(self.lib.editor_click(x,y),0)
        self.assertEqual(self.lib.editor_confirming(),1)
