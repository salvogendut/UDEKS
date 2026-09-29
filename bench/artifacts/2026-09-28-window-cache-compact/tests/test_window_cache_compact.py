# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from window_cache_compact import NAME, PROOF, shared_geometry
from window_cache_acceptance import CASES, decode, negative, page_geometry
from placement_audit import parse_map

class WindowCacheCompactTests(unittest.TestCase):
    def test_geometry_specialization_preserves_c_policy_and_rejects_foreign_records(self):
        harness=r'''
#include <assert.h>
#include <string.h>
#include "udeks/window_cache_flow.h"
#include "udeks/window_cache_command.h"
struct udeks_cache_flow fixed_flow;
struct udeks_cache_lease cache_test_lease;
struct udeks_cache_row cache_test_row;
struct udeks_cache_geometry cache_test_geometry;
uint8_t cache_test_owner,cache_test_eligible,cache_test_params[9],controller_test_phase,flow_test_opcode;
uint16_t cache_test_generation;
static unsigned rows;
void udeks_cache_overlay_row(void) {++rows;}
extern uint8_t udeks_cache_controller(uint8_t);
static void reject_foreign(unsigned paste) {
    struct udeks_cache_flow f=fixed_flow;
    struct udeks_cache_lease l=cache_test_lease;
    struct udeks_cache_row r=cache_test_row;
    struct udeks_cache_geometry g=cache_test_geometry,foreign=g;
    unsigned n=rows;uint8_t owner=cache_test_owner,op=flow_test_opcode;
    uint16_t generation=cache_test_generation;
    assert((paste?udeks_cache_flow_paste(&fixed_flow,1,&foreign):
           udeks_cache_flow_capture(&fixed_flow,1,&foreign,1))==1);
    assert(!memcmp(&f,&fixed_flow,sizeof f) && !memcmp(&l,&cache_test_lease,sizeof l));
    assert(!memcmp(&r,&cache_test_row,sizeof r) && !memcmp(&g,&cache_test_geometry,sizeof g));
    assert(rows==n && owner==cache_test_owner && op==flow_test_opcode && generation==cache_test_generation);
}
static void drive(unsigned phase) {
    for(unsigned i=0;i<104;++i) {
        unsigned n=rows;
        assert(udeks_cache_controller(4)==0 && rows==n+1);
        assert(fixed_flow.phase==(i==103?2:phase));
    }
    assert(udeks_cache_controller(4)==1);
}
int main(void) {
    assert(udeks_cache_controller(0)==0);
    cache_test_geometry=(struct udeks_cache_geometry){7,168,7,104};
    reject_foreign(0);
    assert(udeks_cache_flow_capture(&fixed_flow,1,0,1)==1);
    cache_test_owner=1;cache_test_eligible=1;
    assert(udeks_cache_controller(2)==0);drive(1);
    reject_foreign(1);
    assert(udeks_cache_flow_paste(&fixed_flow,1,0)==1);
    cache_test_geometry.x=100;cache_test_geometry.y=40;
    assert(udeks_cache_controller(3)==0);drive(3);
    cache_test_geometry.x=151;cache_test_geometry.y=83;
    assert(udeks_cache_controller(3)==0);drive(3);assert(rows==312);
    fixed_flow.generation=65535;assert(udeks_cache_controller(1)==0);
    assert(fixed_flow.generation==1 && fixed_flow.phase==0 && cache_test_lease.phase==0);
    reject_foreign(0);
    cache_test_geometry.width=220;cache_test_geometry.height=160;
    assert(udeks_cache_controller(2)==1 && fixed_flow.phase==0);
}
'''
        with tempfile.TemporaryDirectory() as name:
            work=Path(name);source=work/'test.c';source.write_text(harness)
            flow=work/'flow.c';flow.write_text(shared_geometry((PROOF/'src/services/window/move_cache_flow.c').read_text()))
            config=work/'fixed.h';config.write_text('#include "udeks/window_cache_flow.h"\n'
                'extern struct udeks_cache_flow fixed_flow;\n#define UDEKS_CACHE_FLOW_ADDRESS (&fixed_flow)\n'
                '#define flow_test_handle cache_test_owner\n#define flow_test_generation cache_test_generation\n'
                '#define flow_test_geometry cache_test_geometry\n#define flow_test_eligible cache_test_eligible\n')
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-D__fastcall__=',
                '-DUDEKS_CACHE_FLOW_HOST_TEST','-DUDEKS_CACHE_FLOW_IN_BANK',
                '-DUDEKS_CACHE_COMMAND_HOST_TEST','-DUDEKS_CACHE_CONTROLLER_HOST_TEST',
                '-DUDEKS_CACHE_IMAGE_CAPACITY=2224u','-include',str(config),'-I',str(ROOT/'include'),
                str(source),str(flow),str(PROOF/'bench/window-cache-controller/controller.c'),
                str(PROOF/'src/services/window/cache_overlay.c'),str(PROOF/'src/services/window/move_cache_state.c'),
                '-o',str(work/'test')],check=True,capture_output=True)
            subprocess.run([str(work/'test')],check=True,capture_output=True)

    def test_two_carry_dirty_page_formula_and_page_boundaries(self):
        for low in range(256):
            for count in range(1,41):
                length=(count-1)*8
                for high in (0,15,30):
                    result=high+(length>>8)+((low+(length&255))>>8)
                    self.assertEqual(result,((high*256+low)+length)//256)
        for length in (1,255,256,257,3977,4096,4106,4112):
            page,last,calls=page_geometry(length)
            self.assertEqual(page*256+last,length)
            self.assertEqual(page+1,calls)
            self.assertTrue(1<=last<=256)
        with self.assertRaises(ValueError):page_geometry(0)

    def test_linked_allocations_and_fully_charged_compact_budget(self):
        archive=ROOT/'bench/artifacts'/NAME;build=archive/'build'
        report=json.loads((build/'build-report.json').read_text())
        self.assertEqual(report['module_bytes'],4106)
        self.assertEqual(report['gateway_bytes'],196)
        self.assertEqual(report['gateway_source'],0x5146)
        self.assertEqual(report['flow_bytes'],570)
        self.assertEqual(report['identity_slack'],6)
        self.assertEqual(report['resident_bytes'],371)
        self.assertEqual(report['objects']['raw']['CODE'],51)
        self.assertEqual(report['objects']['binding']['CODE'],309)
        self.assertEqual(report['diagnostic_patch_bytes'],11)
        self.assertEqual(report['remaining_before_hooks'],131)
        self.assertEqual(report['page_calls'],17);self.assertEqual(report['last_page_bytes'],10)
        module=archive/'build/bench/window-cache-compact/module.bin'
        gateway=(build/'gateway.bin').read_bytes()
        self.assertEqual(module.read_bytes()[0xf46:],gateway)
        self.assertEqual(module.read_bytes()[:213],(PROOF/'build/module.bin').read_bytes()[:213])
        _,segments=parse_map((archive/'build/bench/window-cache-compact/module.map').read_text())
        layout={n:(s,e) for n,s,e in segments}
        self.assertEqual(layout['GATEIMAGE'],(0x5146,0x5209))
        self.assertEqual(layout['PRIVATESTATE'],(0x5220,0x5239))
        raw=(build/'raw.s').read_text()
        self.assertIn('LOADER = RUN+$d0',raw)
        self.assertIn('GATE_BYTES <= $d0',raw)
        self.assertIn('LOADER+loader_end-loader_image <= PARAM',raw)
        probe=(build/'probe.c').read_text()
        self.assertIn('runtime_accept_count==17',probe)
        self.assertIn('runtime_accept_count==(BADCASE==2?1u:17u)',probe)

    def test_exact_live_controls_both_emulators_and_all_archive_hashes(self):
        archive=ROOT/'bench/artifacts'/NAME;build=archive/'build';results=ROOT/'bench/results'/NAME
        report=json.loads((build/'build-report.json').read_text())
        for group in ('negative_controls','rejection_controls'):
            for name,c in report[group].items():
                original=(build/(f'probe-{name}.original.prg' if group=='rejection_controls' else 'probe-0.prg')).read_bytes()
                bad=(build/f'probe-{name}.prg').read_bytes()
                self.assertEqual(len(original),len(bad))
                self.assertEqual([i for i,(a,b) in enumerate(zip(original,bad)) if a!=b],[c['offset']])
                self.assertEqual(original[c['offset']],c['before']);self.assertEqual(bad[c['offset']],c['after'])
        for key,root in (('source_sha256',archive),('linked_sha256',build),('program_sha256',build)):
            for n,sha in report[key].items():
                self.assertEqual(hashlib.sha256((root/n).read_bytes()).hexdigest(),sha,n)
        for engine in ('1986','vice'):
            record=json.loads((results/f'{engine}-run.json').read_text())
            self.assertEqual(record['build_report_sha256'],hashlib.sha256((build/'build-report.json').read_bytes()).hexdigest())
            self.assertEqual(record['program_sha256'],report['program_sha256'])
            self.assertEqual(set(record['raw_sha256']),{f'{engine}-{c}.bin' for c in CASES})
            for case in CASES:
                path=results/f'{engine}-{case}.bin';data=path.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),record['raw_sha256'][path.name])
                value=decode(data,case,17) if isinstance(case,int) else negative(data,case,17)
                self.assertEqual(value,record['decoded'][str(case)])
        for directory in (archive,results):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                sha,n=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory/n).read_bytes()).hexdigest(),sha,n)
