# SPDX-License-Identifier: GPL-3.0-or-later
import ast
from pathlib import Path
import sys
import tempfile
import unittest
import test_window_repaint_frontend as old
from test_window_cache_manager import compile_run

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
import window_repaint_scenes as scenes

def harness():
    text=old.harness()
    start=text.index('struct udeks_window {');end=text.index('\n};',start)+3
    definition=text[start:end].replace('struct udeks_window {','struct __attribute__((packed)) udeks_window {').replace('unsigned int x;','uint16_t x;').replace('unsigned int width;','uint16_t width;')
    text='#include <stdint.h>\n'+text[:start]+definition+text[end:]
    receipt=(ROOT / 'bench/window-repaint-raster/receipt.c').read_text().replace(
        '#include "../window-repaint-bank/packet.h"','#include "'+str(scenes.SOURCE / 'packet.h')+'"')
    text=text.replace('#include "'+str(ROOT / 'bench/window-repaint-raster/receipt.c')+'"',receipt)
    dispatch=(ROOT / 'bench/window-repaint-bank/dispatch.c').read_text().replace('#include "packet.h"','')
    text=text.replace(dispatch,(scenes.SOURCE / 'dispatch.c').read_text().replace('#include "packet.h"',''))
    front=(ROOT / 'bench/window-repaint-frontend/frontend.inc').read_text()
    text=text.replace(front.replace('#include "../window-repaint-bank/packet.h"',''),
        scenes.frontend(front).replace('#include "../window-repaint-scenes/packet.h"',''))
    return text

def body(name):
    tree=ast.parse((ROOT / 'tests/test_window_repaint_frontend.py').read_text())
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    call=next(n for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='run')
    return ast.literal_eval(call.args[0])

def run(text):
    with tempfile.TemporaryDirectory() as directory:
        return compile_run(Path(directory),'scenes',harness()+text,
            (ROOT / 'src/services/window/move_cache_state.c',ROOT / 'src/services/window/repaint_lane.c'))

class RepaintScenesTests(unittest.TestCase):
    def test_complete_pixels_order_local_work_and_bounded_delegation_match(self):
        text=body('test_actual_view_packing_order_canvas_and_one_step_poll')
        start=text.index('  assert(packet.count==2');end=text.index('\n  switch(',start)
        text=text[:start]+'''  assert(packet.count==0x84 && packet.scenes[1].rank==2 && packet.scenes[3].rank==1);
  assert(packet.scenes[1].x==256 && packet.scenes[1].width==64 && packet.scenes[1].height==104);
  for(unsigned n=0;n<4;++n)assert(packet.reserved[n]==0);
'''+text[end:]
        self.assertEqual(run(text),b'view packing bounded pixels delegation OK\n')

    def test_resource_conflicts_preserve_packet_job_output_and_clip(self):
        self.assertEqual(run(body('test_rejected_leases_and_resource_conflicts_do_not_publish_or_draw')),
            b'resource conflicts atomic OK\n')

    def test_legacy_format_reserved_and_geometry_rejection_before_job_progress(self):
        self.assertEqual(run(r'''
int main(void){
 scene();udeks_lane_init();struct udeks_repaint_rect full={0,320,0,200};
 assert(repaint_frontend_control(1,&full,1)==0);
 struct udeks_repaint_lane_work work;assert(repaint_frontend_poll(1,&work)==0);
 packet.op=REPAINT_PEEK;
 struct udeks_repaint_lane before=udeks_repaint_lane;
 unsigned f=fills,p=page_calls;udeks_vic_bitmap_set_clip(111,77,2,3);
 for(unsigned n=0;n<9;++n){
  packet.count=0x84;memset(packet.reserved,0,4);
  packet.scenes[1].x=256;packet.scenes[1].width=64;packet.scenes[1].height=104;packet.scenes[1].rank=2;
  if(n<3)packet.count=(unsigned char[]){0,4,255}[n];
  else if(n<7)packet.reserved[n-3]=1;
  else if(n==7)packet.scenes[1].x=65535;
  else packet.scenes[1].rank=5;
  assert(private_repaint_policy_call()==2);
  assert(memcmp(&before,&udeks_repaint_lane,sizeof(before))==0 && fills==f && page_calls==p);
  assert(cx0==111 && cy0==77 && cx1==113 && cy1==80);
 }
 /* Prefix metadata cannot contain any title/callback address. */
 windows[1].title=(const unsigned char *)1;windows[1].paint=(udeks_window_paint_fn)1;
 dragging_handle=1;assert(repaint_frontend_poll(1,&work)==7);dragging_handle=0;
 assert(repaint_frontend_control(2,&full,1)==0);windows[1].z=0;
 assert(repaint_frontend_poll(1,&work)==0 && packet.scenes[1].rank==0);
 assert(sizeof(struct repaint_scene)==8 && offsetof(struct udeks_window,title)==8);
 assert(memcmp(&packet.scenes[1],&windows[1],8)==0);
 puts("scene format geometry prefix rejection OK");return 0;
}
'''),b'scene format geometry prefix rejection OK\n')
