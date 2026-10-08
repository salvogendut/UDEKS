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
                        '-I'+str(ROOT/'user/include'),
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

    def finish_stroke(self):
        steps=0
        while self.lib.editor_step():
            self.lib.editor_draw();steps+=1
            self.assertLessEqual(steps,24)
            self.assertEqual(c.c_ubyte.in_dll(self.lib,'editor_op').value,6)

    def test_selected_sprite_number_is_present_in_editor_and_dialogs(self):
        for slot in range(8):
            self.lib.editor_reset(); self.select(slot)
            for action in (None,(220,64),(92,123)):
                if action: self.lib.editor_click(*action)
                count=self.lib.editor_draw()
                self.assertLessEqual(count,63)
                commands=bytes(self.lib.editor_commands()[:count*8])
                digits=[commands[i+3:i+8] for i in range(0,len(commands),8)
                        if commands[i:i+3]==bytes((2,236,24))]
                expected=((2,6,2,2,7),(7,1,7,4,7),(7,1,7,1,7),(5,5,7,1,1),
                          (7,4,7,1,7),(7,4,7,5,7),(7,1,1,1,1),(7,5,7,5,7))
                self.assertEqual(digits,[bytes(expected[slot])])

    def test_held_stroke_paints_interpolates_and_erases_without_repeated_toggle(self):
        self.select(7)
        def event(state,x,y): return self.lib.editor_input(state,8+x*8+4,20+y*8+4)
        self.assertEqual(event(3,0,0),1);self.lib.editor_draw()
        for _ in range(10): self.assertEqual(event(4,0,0),0)
        self.assertEqual(event(4,23,0),1);self.lib.editor_draw();self.finish_stroke()
        self.assertEqual(bytes(self.lib.editor_pixels()[:3]),bytes([255])*3)
        self.assertEqual(event(4,0,0),0) # retrace does not erase
        self.lib.editor_input(1,0,0)
        self.assertEqual(event(4,12,12),0) # new stroke needs a new click
        self.assertEqual(event(3,0,0),1);self.lib.editor_draw()
        self.assertEqual(event(4,23,0),1);self.lib.editor_draw();self.finish_stroke()
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),bytes(63))
        self.lib.editor_input(1,0,0)
        event(3,0,0);self.lib.editor_draw();event(4,20,20);self.lib.editor_draw();self.finish_stroke()
        for y in range(21):
            self.assertTrue(self.lib.editor_pixels()[y*3+y//8] & (128>>(y%8)))

    def test_held_input_never_activates_controls_and_leaving_grid_ends_stroke(self):
        self.select()
        self.lib.editor_input(3,12,24);self.lib.editor_draw()
        for xy in ((220,64),(220,90),(220,116),(220,142),(220,168),(92,123)):
            self.assertEqual(self.lib.editor_input(4,*xy),0)
        self.assertEqual(self.lib.editor_confirming(),0)
        self.assertEqual(self.lib.editor_input(4,20,24),0)
        self.assertEqual(bytes(self.lib.editor_pixels()[:3]),b'\x80\0\0')
        self.lib.editor_input(3,220,64)
        self.assertEqual(self.lib.editor_confirming(),1)
        self.assertEqual(self.lib.editor_input(4,92,123),0)
        self.assertEqual(self.io('calls',word=True),0)

    def test_held_single_cell_keeps_delta_and_stroke_retry_does_not_reapply(self):
        self.select();self.lib.editor_input(3,12,24);self.lib.editor_draw()
        self.assertEqual(self.lib.editor_input(4,20,24),1)
        c.c_ubyte.in_dll(self.lib,'editor_error').value=11
        self.lib.editor_draw()
        self.assertEqual(c.c_ubyte.in_dll(self.lib,'editor_op').value,6)
        c.c_ubyte.in_dll(self.lib,'editor_error').value=0
        self.lib.editor_draw()
        self.assertEqual(self.lib.editor_input(4,20,24),0)
        self.assertEqual(bytes(self.lib.editor_pixels()[:3]),b'\xc0\0\0')

    def test_interpolation_is_bounded_connected_and_monotone_in_every_direction(self):
        targets=((0,0),(23,0),(0,20),(23,20),(1,19),(22,1),(7,20),(23,8),(12,10))
        for start in targets[:4]:
            for end in targets:
                self.lib.editor_reset();self.select()
                self.lib.editor_input(3,12+start[0]*8,24+start[1]*8)
                self.lib.editor_draw()
                self.lib.editor_input(4,12+end[0]*8,24+end[1]*8)
                self.lib.editor_draw();self.finish_stroke()
                pixels=bytes(self.lib.editor_pixels()[:63])
                points={(x,y) for y in range(21) for x in range(24)
                        if pixels[y*3+x//8] & (128>>(x%8))}
                self.assertIn(start,points);self.assertIn(end,points)
                self.assertEqual(len(points),max(abs(start[0]-end[0]),abs(start[1]-end[1]))+1)
                for x,y in points:
                    self.assertTrue(min(start[0],end[0])<=x<=max(start[0],end[0]))
                    self.assertTrue(min(start[1],end[1])<=y<=max(start[1],end[1]))
                    if (x,y)!=end:
                        self.assertTrue(any((x+dx,y+dy) in points and
                            max(abs(x+dx-end[0]),abs(y+dy-end[1]))<max(abs(x-end[0]),abs(y-end[1]))
                            for dx,dy in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))))

    def render(self):
        count = self.lib.editor_draw()
        self.assertLessEqual(count, 63)
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

    def test_pixel_update_has_exact_two_cells_and_retries_without_losing_edit(self):
        self.select()
        self.lib.editor_draw()
        self.lib.editor_click(199,187)
        before=bytes(self.lib.editor_pixels()[:63])
        error=c.c_ubyte.in_dll(self.lib,'editor_error')
        error.value=11
        self.lib.editor_draw()
        self.assertEqual(c.c_ubyte.in_dll(self.lib,'editor_op').value,6)
        request=(c.c_ubyte*38).in_dll(self.lib,'editor_request')
        self.assertEqual(bytes(request[26:36]),bytes((192,180,8,8,0,231,40,1,1,0)))
        error.value=0
        self.lib.editor_draw()
        self.assertEqual(c.c_ubyte.in_dll(self.lib,'editor_op').value,6)
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),before)
        self.lib.editor_draw()
        self.assertEqual(c.c_ubyte.in_dll(self.lib,'editor_op').value,2)
        self.lib.editor_click(199,187); self.lib.editor_draw()
        self.assertEqual(request[30],7)
        self.assertEqual(request[35],7)
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),bytes(63))

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

    def test_save_confirmation_cancel_and_slot_isolation(self):
        self.select(7)
        self.lib.editor_click(199,187)
        edited=bytes(self.lib.editor_pixels()[:63])
        self.lib.editor_click(231,76)  # S, bottom-right of visible button
        self.assertEqual(self.lib.editor_confirming(),1)
        self.assertEqual(self.lib.editor_click(8,20),0)  # freeze edit during prompt
        image=self.render()
        self.assertEqual(image[116*248+76],0)  # Y remains visibly framed
        self.assertEqual(image[116*248+134],0)  # N remains visibly framed
        self.lib.editor_click(150,123)  # N cancels prompt, not the edit
        self.assertEqual(self.lib.editor_mode(),1)
        self.assertEqual(self.lib.editor_confirming(),0)
        self.assertEqual(bytes(self.lib.editor_bank()[:504]),bytes(504))
        self.lib.editor_click(208,52);self.lib.editor_click(92,123)
        self.assertEqual(self.lib.editor_confirming(),3)
        self.assertEqual(c.c_ubyte.in_dll(self.lib,'udeks_xsprdef_file_error').value,0)
        self.lib.editor_click(92,123) # dismiss DONE
        self.assertEqual(bytes(self.lib.editor_bank()[:441]),bytes(441))
        self.assertEqual(bytes(self.lib.editor_bank()[441:504]),edited)
        self.lib.editor_click(8,20)
        updated=bytes(self.lib.editor_pixels()[:63])
        self.lib.editor_click(208,78)  # keep working changes in session bank
        self.select(7)
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),updated)

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

    def io(self,name,value=None,word=False):
        cell=(c.c_ushort if word else c.c_ubyte).in_dll(self.lib,'io_'+name)
        if value is not None: cell.value=value
        return cell.value

    def file_data(self,size=504):
        data=bytes((i*73+19)&255 for i in range(size))
        c.memmove((c.c_ubyte*600).in_dll(self.lib,'io_data'),data,len(data))
        self.io('length',len(data),True)
        return data

    def test_disk_save_exact_raw_bank_and_close(self):
        expected=self.file_data()
        source=(c.c_ubyte*506)(91,*expected,37)
        self.assertEqual(self.lib.editor_file(1,c.byref(source,1)),0)
        self.assertEqual(self.io('flags'),3)
        self.assertEqual(self.io('offset',word=True),504)
        self.assertEqual(self.io('closes',word=True),1)
        self.assertEqual(bytes((c.c_ubyte*600).in_dll(self.lib,'io_written'))[:504],expected)
        self.assertEqual((source[0],source[505]),(91,37))
        self.assertEqual(self.io('invalid'),0)

    def test_disk_read_accepts_short_chunks_but_requires_exact_eof(self):
        for chunk in (1,7,23,24):
            self.lib.editor_io_reset();expected=self.file_data()
            self.io('chunk',chunk)
            target=(c.c_ubyte*506)(*([0xa5]*506))
            self.assertEqual(self.lib.editor_file(0,c.byref(target,1)),0)
            self.assertEqual(bytes(target[1:505]),expected)
            self.assertEqual((target[0],target[505]),(0xa5,0xa5))
            self.assertEqual(self.io('closes',word=True),1)
            self.assertEqual(self.io('flags'),0)
            self.assertEqual(self.io('invalid'),0)

    def test_transfer_errors_short_writes_and_close_never_report_success(self):
        for save in (0,1):
            for failure in range(1,23 if save else 24):
                self.lib.editor_io_reset();self.file_data()
                self.io('fail_at',failure,True);self.io('error',19)
                self.io('close_error',5) # preserve the original transfer error
                target=(c.c_ubyte*504)()
                self.assertEqual(self.lib.editor_file(save,target),19,(save,failure))
                self.assertEqual(self.io('closes',word=True),int(failure!=1))
            self.lib.editor_io_reset();self.file_data();self.io('close_error',5)
            self.assertEqual(self.lib.editor_file(save,(c.c_ubyte*504)()),5)
            for failure in range(2,23):
                self.lib.editor_io_reset();self.file_data();self.io('over_at',failure,True)
                self.assertEqual(self.lib.editor_file(save,(c.c_ubyte*504)()),5)
            for failure in range(2,23):
                self.lib.editor_io_reset();self.io('short_at',failure,True)
                self.assertEqual(self.lib.editor_file(1,(c.c_ubyte*504)()),5)
                self.assertEqual(self.io('closes',word=True),1)

    def test_failed_load_never_commits_bank_or_current_edit(self):
        for size in (0,1,503,505,600,504):
            self.lib.editor_reset();self.select(7);self.lib.editor_click(199,187)
            bank=bytes([0x81])*504;c.memmove(self.lib.editor_bank(),bank,504)
            edit=bytes(self.lib.editor_pixels()[:63])
            self.file_data(size)
            if size==504: self.io('close_error',5)
            self.lib.editor_click(231,180) # L at bottom-right
            self.assertEqual(self.lib.editor_confirming(),2)
            self.assertEqual(self.io('calls',word=True),0)
            self.lib.editor_click(92,123) # Y
            self.assertEqual(self.lib.editor_confirming(),3)
            self.assertEqual(c.c_ubyte.in_dll(self.lib,'udeks_xsprdef_file_error').value,5 if size==504 else 8)
            self.assertEqual(bytes(self.lib.editor_bank()[:504]),bank)
            self.assertEqual(bytes(self.lib.editor_pixels()[:63]),edit)
            self.assertEqual(self.io('closes',word=True),1)

    def test_load_cancel_and_success_refresh_selected_editor(self):
        self.select(4);self.lib.editor_click(8,20)
        edit=bytes(self.lib.editor_pixels()[:63]);expected=self.file_data()
        self.lib.editor_click(208,156);self.render()
        for x,y in ((8,20),(76,115),(75,116),(116,116),(174,116),(92,140)):
            self.assertEqual(self.lib.editor_click(x,y),0)
        self.lib.editor_click(173,139) # N includes full visible edge
        self.assertEqual(self.io('calls',word=True),0)
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),edit)
        self.lib.editor_click(208,156);self.lib.editor_click(115,139)
        self.assertEqual(self.lib.editor_confirming(),3)
        self.assertEqual(bytes(self.lib.editor_bank()[:504]),expected)
        self.assertEqual(bytes(self.lib.editor_pixels()[:63]),expected[4*63:5*63])
        self.lib.editor_click(92,123);self.assertEqual(self.lib.editor_confirming(),0)

    def test_basic_export_has_load_address_and_eight_padded_blocks(self):
        patterns=[bytes(504),bytes([255])*504,self.file_data()]
        for bank in patterns:
            self.lib.editor_io_reset()
            source=(c.c_ubyte*506)(91,*bank,37)
            self.assertEqual(self.lib.editor_file(2,c.byref(source,1)),0)
            expected=b'\x00\x0e'+b''.join(bank[n:n+63]+b'\0' for n in range(0,504,63))
            written=bytes((c.c_ubyte*600).in_dll(self.lib,'io_written'))
            self.assertEqual(written[:514],expected)
            self.assertEqual(written[514:],bytes(86))
            self.assertEqual(self.io('offset',word=True),514)
            self.assertEqual(self.io('calls',word=True),24) # open, 22 writes, close
            self.assertEqual(self.io('closes',word=True),1)
            self.assertEqual((self.io('basic'),self.io('flags'),self.io('invalid')),(1,4,0))
            self.assertEqual(bytes(source),bytes((91,))+bank+bytes((37,)))

    def test_basic_export_checks_every_transfer_and_close(self):
        source=(c.c_ubyte*504)(*self.file_data())
        for field,error in (('fail_at',19),('short_at',5),('over_at',5)):
            for failure in range(1 if field=='fail_at' else 2,24):
                self.lib.editor_io_reset()
                self.io(field,failure,True);self.io('error',19);self.io('close_error',28)
                self.assertEqual(self.lib.editor_file(2,source),error,(field,failure))
                self.assertEqual(self.io('closes',word=True),int(failure!=1))
                self.assertEqual(self.io('calls',word=True),failure+int(failure!=1))
        self.lib.editor_io_reset();self.io('close_error',5)
        self.assertEqual(self.lib.editor_file(2,source),5)

    def test_basic_export_list_confirmation_cancel_and_session_edits(self):
        self.select(7);self.lib.editor_click(199,187)
        self.lib.editor_click(208,78) # B commits current edit before export
        before=bytes(self.lib.editor_bank()[:504])
        for x,y in ((199,120),(224,120),(200,119),(200,145)):
            self.assertEqual(self.lib.editor_click(x,y),0)
        self.assertEqual(self.lib.editor_click(223,144),1)
        self.assertEqual(self.lib.editor_confirming(),4)
        self.render()
        for x,y in ((30,80),(208,156),(80,140)):
            self.assertEqual(self.lib.editor_click(x,y),0)
        self.lib.editor_click(150,123)
        self.assertEqual(self.io('calls',word=True),0)
        self.assertEqual(bytes(self.lib.editor_bank()[:504]),before)
        self.lib.editor_click(200,120);self.lib.editor_click(92,123)
        self.assertEqual(self.lib.editor_confirming(),3)
        self.assertEqual(self.io('basic'),1)
        self.assertEqual(bytes((c.c_ubyte*600).in_dll(self.lib,'io_written'))[513],0)
        self.assertEqual(bytes((c.c_ubyte*600).in_dll(self.lib,'io_written'))[512],1)
        self.render();self.lib.editor_click(92,123)
        self.lib.editor_io_reset();self.lib.editor_click(80,120);self.lib.editor_click(92,123)
        self.assertEqual(self.io('basic'),0) # S still writes the compact file
        self.assertEqual(self.io('offset',word=True),504)

    def test_list_save_load_and_all_result_dialogs_are_bounded(self):
        self.lib.editor_click(103,144);self.assertEqual(self.lib.editor_confirming(),1)
        self.lib.editor_click(150,123);self.assertEqual(self.io('calls',word=True),0)
        self.lib.editor_click(163,144);self.assertEqual(self.lib.editor_confirming(),2)
        self.file_data();self.lib.editor_click(92,123)
        for error in (0,2,5,8,16,17,28,30):
            c.c_ubyte.in_dll(self.lib,'udeks_xsprdef_file_error').value=error
            self.render()
