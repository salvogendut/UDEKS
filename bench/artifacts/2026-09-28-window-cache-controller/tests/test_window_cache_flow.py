# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowCacheFlowTests(unittest.TestCase):
    def test_actual_c_flow_policy_and_command_tickets_wrap_and_single_rows(self):
        harness = r'''
#include <assert.h>
#include <string.h>
#include "udeks/window_cache_flow.h"
#include "udeks/window_cache_command.h"
struct udeks_cache_lease cache_test_lease;
struct udeks_cache_row cache_test_row;
struct udeks_cache_geometry cache_test_geometry, flow_test_geometry;
uint8_t cache_test_owner, cache_test_eligible, cache_test_params[9];
uint16_t cache_test_generation, flow_test_generation;
uint8_t flow_test_opcode, flow_test_handle, flow_test_eligible;
static unsigned calls, rows;
static int fault=-1;
void udeks_cache_overlay_row(void) {++rows;}
uint8_t private_cache_policy_call(void) {
    ++calls;
    cache_test_owner=flow_test_handle;cache_test_generation=flow_test_generation;
    cache_test_geometry=flow_test_geometry;cache_test_eligible=flow_test_eligible;
    if(fault>=0 && flow_test_opcode==4) return (uint8_t)fault;
    return udeks_cache_overlay_command(flow_test_opcode);
}
static void stale(struct udeks_cache_flow *f,unsigned h,unsigned generation) {
    struct udeks_cache_flow old=*f;
    struct udeks_cache_lease lease=cache_test_lease;
    struct udeks_cache_row row=cache_test_row;
    unsigned c=calls,r=rows;
    uint8_t op=flow_test_opcode,owner=flow_test_handle,eligible=flow_test_eligible;
    uint16_t g=flow_test_generation;
    struct udeks_cache_geometry geometry=flow_test_geometry;
    assert(udeks_cache_flow_step(f,h,generation)==1);
    assert(!memcmp(f,&old,sizeof old) && !memcmp(&lease,&cache_test_lease,sizeof lease));
    assert(!memcmp(&row,&cache_test_row,sizeof row) && c==calls && r==rows);
    assert(op==flow_test_opcode && owner==flow_test_handle && g==flow_test_generation);
    assert(eligible==flow_test_eligible && !memcmp(&geometry,&flow_test_geometry,sizeof geometry));
}
static void drive(struct udeks_cache_flow *f,unsigned height,unsigned phase) {
    for(unsigned i=0;i<height;++i) {
        unsigned c=calls,r=rows;
        assert(udeks_cache_flow_step(f,f->handle,f->generation)==0);
        assert(calls==c+1 && rows==r+1);
        assert(f->phase==(i+1==height?2:phase));
    }
    stale(f,f->handle,f->generation);
}
int main(void) {
    struct udeks_cache_flow f={0};
    struct udeks_cache_geometry g={7,168,7,104};
    assert(sizeof f==4 && udeks_cache_flow_init(&f)==0);
    assert(f.generation==1 && f.phase==0 && f.handle==0);
    for(unsigned h=0;h<6;++h) {
        unsigned c=calls;
        if(h==0 || h>4) assert(udeks_cache_flow_capture(&f,h,&g,1)==1 && calls==c);
    }
    assert(udeks_cache_flow_capture(&f,1,&g,0)==1);
    assert(udeks_cache_flow_capture(&f,1,0,1)==1);
    f.generation=0;assert(udeks_cache_flow_capture(&f,1,&g,1)==1);f.generation=1;
    assert(udeks_cache_flow_capture(&f,1,&g,1)==0 && f.phase==1);
    unsigned c=calls;
    assert(udeks_cache_flow_capture(&f,2,&g,1)==2 && calls==c);
    stale(&f,0,1);stale(&f,2,1);stale(&f,1,0);stale(&f,1,2);
    drive(&f,104,1);
    struct udeks_cache_flow old=f;
    assert(udeks_cache_flow_paste(&f,1,0)==1 && !memcmp(&f,&old,sizeof f));
    assert(udeks_cache_flow_paste(&f,2,&g)==1 && !memcmp(&f,&old,sizeof f));
    g.width=169;assert(udeks_cache_flow_paste(&f,1,&g)==1 && !memcmp(&f,&old,sizeof f));
    g.width=168;g.x=100;g.y=40;
    assert(udeks_cache_flow_paste(&f,1,&g)==0 && f.phase==3);
    assert(udeks_cache_flow_capture(&f,1,&g,1)==2);
    drive(&f,104,3);g.x=151;g.y=83;
    assert(udeks_cache_flow_paste(&f,1,&g)==0);drive(&f,104,3);
    assert(rows==312);
    /* Cancellation invalidates before reuse, including the 16-bit wrap. */
    assert(udeks_cache_flow_paste(&f,1,&g)==0);
    assert(udeks_cache_flow_step(&f,1,1)==0);
    udeks_cache_flow_invalidate(&f);
    assert(f.generation==2 && f.handle==0 && f.phase==0 && cache_test_lease.phase==0);
    stale(&f,1,1);assert(udeks_cache_flow_capture(&f,1,&g,1)==0);stale(&f,1,1);
    udeks_cache_flow_invalidate(&f);
    f.generation=65535;
    assert(udeks_cache_flow_capture(&f,4,&g,1)==0);
    udeks_cache_flow_invalidate(&f);
    assert(f.generation==1 && cache_test_lease.phase==0);stale(&f,4,65535);
    /* No fallback turns an oversized or out-of-screen image into a cache. */
    g.width=220;g.height=160;old=f;
    assert(udeks_cache_flow_capture(&f,4,&g,1)==1 && !memcmp(&f,&old,sizeof f));
    g.width=168;g.height=104;g.x=319;
    assert(udeks_cache_flow_capture(&f,4,&g,1)==1 && !memcmp(&f,&old,sizeof f));
    g.x=7;g.y=7;
    /* All unexpected success tags/WRITTEN flags/errors cancel the lease. */
    for(unsigned phase=1;phase<=3;phase+=2) {
        for(int response=0;response<256;++response) {
            if(response==(phase==1?0x81:0xc3) || response==(phase==1?0x82:0xc2)) continue;
            fault=-1;assert(udeks_cache_flow_init(&f)==0);
            assert(udeks_cache_flow_capture(&f,1,&g,1)==0);
            if(phase==3) {drive(&f,104,1);assert(udeks_cache_flow_paste(&f,1,&g)==0);}
            fault=response;unsigned r=rows;
            assert(udeks_cache_flow_step(&f,1,1)==1 && rows==r);
            assert(f.phase==0 && f.handle==0 && f.generation==2 && cache_test_lease.phase==0);
        }
    }
}
'''
        with tempfile.TemporaryDirectory() as name:
            work = Path(name); source = work / 'test.c'; source.write_text(harness)
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-D__fastcall__=',
                '-DUDEKS_CACHE_FLOW_HOST_TEST', '-DUDEKS_CACHE_COMMAND_HOST_TEST',
                '-I', str(ROOT / 'include'), str(source),
                str(ROOT / 'src/services/window/move_cache_flow.c'),
                str(ROOT / 'src/services/window/cache_overlay.c'),
                str(ROOT / 'src/services/window/move_cache_state.c'), '-o', str(work / 'test')],
                check=True, capture_output=True)
            subprocess.run([str(work / 'test')], check=True, capture_output=True)
            # Replay the entire same contract against the fixed-state,
            # direct-call specialization, including fault-tag injection.
            config = work / 'fixed.h'
            config.write_text('#include "udeks/window_cache_flow.h"\n'
                'extern struct udeks_cache_flow fixed_flow;\n'
                '#define UDEKS_CACHE_FLOW_ADDRESS (&fixed_flow)\n')
            fixed = harness.replace('int main(void) {',
                'struct udeks_cache_flow fixed_flow;\n'
                'uint8_t flow_direct_command(uint8_t op) {\n'
                'flow_test_opcode=op;return private_cache_policy_call();}\n'
                '#define f fixed_flow\nint main(void) {').replace(
                'struct udeks_cache_flow f={0};',
                'f=(struct udeks_cache_flow){0};')
            source.write_text(fixed)
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                '-D__fastcall__=', '-DUDEKS_CACHE_FLOW_HOST_TEST', '-DUDEKS_CACHE_FLOW_IN_BANK',
                '-Dudeks_cache_overlay_command=flow_direct_command', '-include', str(config),
                '-I', str(ROOT / 'include'), '-c', str(ROOT / 'src/services/window/move_cache_flow.c'),
                '-o', str(work / 'flow.o')], check=True, capture_output=True)
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-D__fastcall__=',
                '-DUDEKS_CACHE_FLOW_HOST_TEST', '-DUDEKS_CACHE_COMMAND_HOST_TEST',
                '-DUDEKS_CACHE_IMAGE_CAPACITY=2224u', '-I', str(ROOT / 'include'),
                str(source), str(work / 'flow.o'), str(ROOT / 'src/services/window/cache_overlay.c'),
                str(ROOT / 'src/services/window/move_cache_state.c'), '-o', str(work / 'fixed')],
                check=True, capture_output=True)
            subprocess.run([str(work / 'fixed')], check=True, capture_output=True)
