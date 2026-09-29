# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_manager_budget import BASE, NAME, variant
from placement_audit import parse_map
from gen_capability_imports import map_exports
from nmi_integration_probe import inspect_nmi
from window_completion_probe import inspect as inspect_completion
from graphics_cache_placement import audit, listing_functions


class WindowManagerBudgetTests(unittest.TestCase):
    def test_public_abi_and_each_transform_are_bounded(self):
        source = BASE.read_text()
        self.assertEqual(variant(source, 'baseline'), source)
        fast = variant(source, 'fastcall')
        # Existing public completion ABI remains the only public fastcall entry.
        self.assertEqual([s for s in fast.splitlines() if '__fastcall__' in s and not s.startswith('static')],
            [s for s in source.splitlines() if '__fastcall__' in s and not s.startswith('static')])
        with self.assertRaises(ValueError):
            variant(source.replace('static void draw_chrome(', 'static void changed_chrome('), 'lean')
        with self.assertRaises(ValueError):
            variant(source, 'unknown')

    def test_real_c_manager_matches_baseline_geometry_state_and_all_drawing_calls(self):
        harness = r'''
#include <stdio.h>
#include <stdint.h>
static unsigned char test_status[32];
SOURCE
static uint64_t trace=1469598103934665603ULL;
static unsigned px=172,py=140,buttons;
static void mix(unsigned value) {
    unsigned char bytes[4]={value,value>>8,value>>16,value>>24};
    fwrite(bytes,1,4,stdout); /* Compare the complete trace, not just a digest. */
    trace^=value;trace*=1099511628211ULL;
}
static void draw(unsigned op,int a,int b,int c,int d,int e)
{mix(op);mix(a);mix(b);mix(c);mix(d);mix(e);}
void udeks_vic_bitmap_set_clip(int x,int y,int w,int h) {draw(1,x,y,w,h,0);}
void udeks_vic_bitmap_reset_clip(void) {mix(2);}
void udeks_vic_bitmap_commit(void) {mix(3);}
void udeks_vic_bitmap_fill(int x,int y,int w,int h,unsigned char c) {draw(4,x,y,w,h,c);}
void udeks_vic_bitmap_pixel(int x,int y,unsigned char c) {draw(5,x,y,c,0,0);}
void udeks_vic_bitmap_line(int x,int y,int xx,int yy,unsigned char c) {draw(6,x,y,xx,yy,c);}
void udeks_vic_bitmap_rectangle(int x,int y,int w,int h,unsigned char c) {draw(7,x,y,w,h,c);}
void udeks_vic_pointer_busy_begin(unsigned char reason) {draw(8,reason,0,0,0,0);}
void udeks_vic_pointer_busy_end(unsigned char reason) {draw(9,reason,0,0,0,0);}
void udeks_vic_bitmap_outline_toggle(unsigned x,unsigned char y,unsigned w,unsigned char h)
{draw(10,x,y,w,h,0);}
void udeks_vic_bitmap_outline_move(unsigned x,unsigned char y,unsigned xx,unsigned char yy,
 unsigned w,unsigned char h) {draw(11,x,y,xx,yy,w);mix(h);}
unsigned char udeks_vic_graphics_is_active(void) {return 1;}
unsigned int udeks_pointer_x(void) {return px;}
unsigned char udeks_pointer_y(void) {return py;}
unsigned char udeks_pointer_buttons(void) {return buttons;}
void udeks_pointer_resynchronize(void) {mix(12);}
static void paint(unsigned char handle) {mix(13);mix(handle);}
static void closed(unsigned char handle) {mix(14);mix(handle);}
static uint32_t seed=0x19365428u;
static unsigned rnd(void) {seed=seed*1664525u+1013904223u;return seed>>16;}
static void state(void) {
    for(unsigned i=0;i<32;++i)mix(test_status[i]);
    for(unsigned i=0;i<4;++i) {
        struct udeks_window *w=&windows[i];
        mix(w->active);mix(w->owner);mix(w->surface);mix(w->flags);mix(w->x);mix(w->y);
        mix(w->width);mix(w->height);mix(w->z);
    }
    mix(active_count);mix(focused_handle);mix(dragging_handle);mix(previous_buttons);
    mix(drag_pointer_x);mix(drag_pointer_y);mix(drag_x);mix(drag_y);
    mix(drag_width);mix(drag_height);mix(drag_mode);
    mix(damage_left);mix(damage_top);mix(damage_right);mix(damage_bottom);
}
int main(void) {
    mix(udeks_window_manager_start());state();
    /* Every min/max geometry and title clipping size, plus all public flags. */
    for(unsigned width=16;width<=320;++width) {
        unsigned x=320-width,y=(width%180),height=200-y;
        unsigned handle=udeks_window_create(1,1,width&15,x,y,width,height,
            (const unsigned char *)"aZ! clock wave",paint,closed);
        mix(handle);mix(udeks_window_image_complete(handle));
        mix(udeks_window_begin_paint(handle));udeks_window_end_paint();
        mix(udeks_window_destroy(handle));state();
    }
    for(unsigned i=0;i<800;++i) {
        unsigned handle=1+rnd()%4;
        switch(rnd()%8) {
        case 0:mix(udeks_window_create(1+rnd()%2,1,rnd()&255,rnd()%300,rnd()%180,
              16+rnd()%300,18+rnd()%180,(const unsigned char *)"Wave CLOCK",paint,closed));break;
        case 1:mix(udeks_window_destroy(handle));break;
        case 2:mix(udeks_window_repaint(handle));break;
        case 3:mix(udeks_window_image_complete(handle));break;
        case 4:mix(udeks_window_begin_paint(handle));udeks_window_end_paint();break;
        case 5: {struct udeks_window *w=window_by_handle(handle);
            if(w) {
                /* Alternating move, resize and close hits; use actual poll routing. */
                px=w->x+12+(i%3==0?w->width-7:(i%3==1?w->width-10:8));
                py=w->y+40+(i%3==0?w->height-7:6);buttons=1;
                mix(udeks_window_manager_poll());
                for(unsigned n=0;n<3;++n) {px=12+rnd()%320;py=40+rnd()%200;
                    mix(udeks_window_manager_poll());}
                buttons=0;mix(udeks_window_manager_poll());
            }break;}
        case 6: {unsigned x,w;unsigned char y,h;
            unsigned ok=udeks_window_get_geometry(handle,&x,&y,&w,&h);mix(ok);
            if(!ok) {mix(x);mix(y);mix(w);mix(h);}break;}
        case 7:mix(udeks_window_manager_stop());mix(udeks_window_manager_start());break;
        }
        state();
    }
    printf("%016llx\n",(unsigned long long)trace);
}
'''
        source = BASE.read_text()
        with tempfile.TemporaryDirectory() as name:
            work = Path(name); traces = []
            for label, manager in (('baseline', source), ('lean', variant(source, 'lean'))):
                manager = manager.replace(
                    '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))',
                    'test_status[offset]')
                path = work / (label+'.c'); path.write_text(harness.replace('SOURCE', manager))
                result = subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
                    '-Wno-unknown-pragmas','-D__fastcall__=','-I',str(ROOT / 'include'),
                    str(path),'-o',str(work / label)], capture_output=True, text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                traces.append(subprocess.check_output([str(work / label)]))
            self.assertEqual(traces[0],traces[1])

    def test_preserved_sizes_inputs_and_whole_link_shortfall(self):
        directory = ROOT / 'bench/artifacts' / NAME
        report = json.loads((directory / 'build/report.json').read_text())
        self.assertEqual(report['results']['fastcall']['code_saved'], 0)
        self.assertEqual({n: report['results'][n]['code_saved'] for n in ('reset','chrome','intersection','lean')},
            dict(reset=58,chrome=145,intersection=18,lean=221))
        for result in report['results'].values():
            self.assertEqual(result['imports_added'],[])
            self.assertEqual(result['segments']['HIGHBSS'],88)
        self.assertEqual(report['available_after_savings'],502)
        # This is a lower bound: no actual compositor hooks/delivery/locks yet.
        size=sum(report['flow_segments'].values())+report['flow_state_bytes']+report['resident_binding_bytes']
        self.assertEqual(report['experimental_bank0_shortfall'],size-502)
        self.assertEqual(report['helpers_added'],{})
        new={name:(start,end) for name,start,end in parse_map((directory / 'build/experimental.map').read_text())[1]}
        self.assertEqual(new['VICSHADOW'][0]-0xa1e0, report['experimental_bank0_shortfall'])
        for name,sha in report['source_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)
        for name,sha in report['output_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / 'build' / name).read_bytes()).hexdigest(),sha,name)
        for line in (directory / 'SHA256SUMS').read_text().splitlines():
            sha,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)

    def test_installed_savings_frozen_segments_runtime_and_emulator_gates(self):
        name='2026-09-28-window-manager-integration'
        directory=ROOT / 'bench/artifacts' / name
        results=ROOT / 'bench/results' / name
        previous=ROOT / 'bench/artifacts/2026-09-28-nmi-integration'
        old,old_segments=parse_map((previous / 'build/8502/udeks-8502.map').read_text())
        text=(directory / 'build/8502/udeks-8502.map').read_text()
        modules,segments=parse_map(text)
        self.assertEqual(segments,old_segments)
        self.assertEqual(modules['window_manager.o'],{'CODE':7679,'RODATA':130,'HIGHBSS':88})
        self.assertEqual(modules['vic_graphics_transport.o']['CODE'],old['vic_graphics_transport.o']['CODE']+221)
        for module in old:
            if module not in ('window_manager.o','vic_graphics_transport.o'):
                self.assertEqual(modules[module],old[module],module)
        self.assertEqual(parse_map((directory / 'build/8502/udeks-8502-panic-probe.map').read_text())[1],segments)
        report=json.loads((directory / 'build-report.json').read_text())
        self.assertEqual((report['remaining_padding'],report['remaining_before_manager_delivery']),(502,261))
        self.assertNotIn('flow.o',modules)
        # Historical integration evidence stays immutable. The later
        # production delta is limited to the 16-bit-safe create bound and two
        # source-level compactions that recover its bytes without moving the
        # fixed boot/shadow layout.
        qualified = variant(BASE.read_text(), 'lean')
        edits = (
            ('x + width > UDEKS_VIC_WIDTH ||',
             'x > UDEKS_VIC_WIDTH || width > UDEKS_VIC_WIDTH - x ||'),
            ('''    if (handle == UDEKS_WINDOW_NONE || handle > UDEKS_WINDOW_MAX ||
        windows[handle - 1u].active == 0) {
        return 0;
    }
    return &windows[handle - 1u];''',
             '''    --handle; /* Zero wraps to 255 and fails the bounded index check. */
    if (handle >= UDEKS_WINDOW_MAX || windows[handle].active == 0) {
        return 0;
    }
    return &windows[handle];'''),
            ('''window->flags = (unsigned char)((flags & 0x0Fu) | UDEKS_WINDOW_FLAG_VISIBLE |
        UDEKS_WINDOW_FLAG_RESIZABLE);''',
             '''window->flags = (unsigned char)((flags & 0x0Fu) |
        (UDEKS_WINDOW_FLAG_VISIBLE | UDEKS_WINDOW_FLAG_RESIZABLE));'''),
        )
        for before, after in edits:
            self.assertEqual(qualified.count(before), 1)
            qualified = qualified.replace(before, after)
        self.assertEqual((ROOT / 'src/services/window/window_manager.c').read_text(),
                         qualified)
        expected={'sp':6,'sreg':8,'regsave':10,'ptr1':14,'ptr2':16,'ptr3':18,'ptr4':20,
            'tmp1':22,'tmp2':23,'tmp3':24,'tmp4':25,'regbank':26}
        exports=map_exports(text)
        self.assertEqual({symbol:exports[symbol][0] for symbol in expected},expected)
        for path in (directory,results):
            for line in (path / 'SHA256SUMS').read_text().splitlines():
                sha,filename=line.split('  ',1)
                self.assertEqual(hashlib.sha256((path / filename).read_bytes()).hexdigest(),sha,filename)
        for filename,sha in report['inputs_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / filename).read_bytes()).hexdigest(),sha,filename)
        for engine in ('1986','vice'):
            run=json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['build_report_sha256'],hashlib.sha256((directory / 'build-report.json').read_bytes()).hexdigest())
            for filename,sha in run['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results / filename).read_bytes()).hexdigest(),sha,filename)
            for fmt in ('d71','d64'):
                value={**inspect_nmi((results / f'{engine}-{fmt}-nmi.bin').read_bytes()),
                    **inspect_completion((results / f'{engine}-{fmt}-windows.bin').read_bytes(),
                        (results / f'{engine}-{fmt}-gateway.bin').read_bytes(),report['completion_entry'])}
                self.assertEqual(value,run['decoded'][fmt])
                self.assertEqual(hashlib.sha256((directory / f'udeks.{fmt}').read_bytes()).hexdigest(),report['disk_sha256'][fmt])
        # The same disk passed the independent layout gate. Reconstruct its
        # exact budget and reject a manager-size drift rather than silently
        # granting extra padding to another implementation.
        layout=ROOT / 'bench/results' / (name+'-layout')
        facts=json.loads((layout / 'report.json').read_text())
        self.assertEqual(facts['disk_sha256'],report['disk_sha256']['d71'])
        self.assertEqual(facts['remaining_padding'],502)
        self.assertFalse(any((layout / 'shadow-boot.bin').read_bytes()[:8000]))
        self.assertEqual((layout / 'shadow-drawn.bin').read_bytes(),(layout / 'vic-bitmap.bin').read_bytes())
        for line in (layout / 'SHA256SUMS').read_text().splitlines():
            sha,filename=line.split('  ',1)
            self.assertEqual(hashlib.sha256((layout / filename).read_bytes()).hexdigest(),sha,filename)
        from test_graphics_cache_placement import inputs
        args=inputs();args[0]=text
        args[10]=listing_functions((layout / 'raster.lst').read_text())
        args[12]=[(layout / f'{n}.segments.txt').read_text() for n in ('cache','rows','transfer')]
        placement=json.loads((layout / 'placement.json').read_text())
        providers=placement['integrated_primitives']
        actual=audit(*args,primitives=providers,primitive_reserve=173,shared_reserve=280)
        self.assertEqual(actual,{name:placement[name] for name in actual})
        args[0]=text.replace('Size=001DFF','Size=001E00') # 7679 -> 7680
        self.assertNotEqual(args[0],text)
        with self.assertRaisesRegex(ValueError,'window-manager savings'):
            audit(*args,primitives=providers,primitive_reserve=173,shared_reserve=280)
