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
from window_cache_controller import NAME, CASES, decode, negative
from window_cache_command import reference
from placement_audit import parse_map
from gen_capability_imports import map_exports

def synthetic(case=0):
    data = bytearray(8096); data[:8] = b'CTRL\x01\x02'+bytes((case, 0))
    rows, calls, images = (132, 476, 66) if case == 0 else (312, 333, 2)
    data[8:10] = rows.to_bytes(2, 'little'); data[10:12] = calls.to_bytes(2, 'little')
    data[12] = 1; data[14] = images; data[22] = 204; data[23] = 15
    data[26] = 2; data[30] = 1; data[34] = 2; data[64:] = reference(case)
    return data

class WindowCacheControllerTests(unittest.TestCase):
    def test_real_fixed_controller_direct_backend_and_rejection(self):
        harness = r'''
#include <assert.h>
#include <string.h>
#include "udeks/window_cache_flow.h"
#include "udeks/window_cache_command.h"
struct udeks_cache_flow fixed_flow;
struct udeks_cache_lease cache_test_lease;
struct udeks_cache_row cache_test_row;
struct udeks_cache_geometry cache_test_geometry;
uint8_t cache_test_owner,cache_test_eligible,cache_test_params[9],controller_test_phase;
uint16_t cache_test_generation;
uint8_t flow_test_opcode;
static unsigned rows;
void udeks_cache_overlay_row(void) {++rows;}
extern uint8_t udeks_cache_controller(uint8_t);
static uint8_t call(unsigned op,unsigned h,unsigned gen) {
    cache_test_owner=h;cache_test_generation=gen;
    return udeks_cache_controller(op);
}
static void reject(unsigned op,unsigned h,unsigned gen,unsigned expected) {
    cache_test_owner=h;cache_test_generation=gen;
    struct udeks_cache_flow f=fixed_flow;
    struct udeks_cache_lease l=cache_test_lease;
    struct udeks_cache_row r=cache_test_row;
    unsigned previous=rows,phase=controller_test_phase;
    assert(udeks_cache_controller(op)==expected);
    assert(!memcmp(&f,&fixed_flow,sizeof f) && !memcmp(&l,&cache_test_lease,sizeof l));
    assert(!memcmp(&r,&cache_test_row,sizeof r) && rows==previous);
    assert(cache_test_owner==h && cache_test_generation==gen && controller_test_phase==phase);
}
static void drive(unsigned mode) {
    for(unsigned i=0;i<104;++i) {
        unsigned previous=rows;
        assert(call(4,1,fixed_flow.generation)==0 && rows==previous+1);
        assert(controller_test_phase==(i==103?2:mode));
        assert(cache_test_generation==fixed_flow.generation);
    }
    reject(4,1,fixed_flow.generation,1);
}
int main(void) {
    assert(call(0,0,0)==0 && cache_test_generation==1 && controller_test_phase==0);
    assert(cache_test_lease.capacity==2224);
    cache_test_geometry=(struct udeks_cache_geometry){7,168,7,104};
    cache_test_eligible=0;reject(2,1,99,1);
    cache_test_eligible=1;assert(call(2,1,99)==0 && cache_test_generation==1);
    reject(4,1,2,1);reject(4,2,1,1);reject(255,1,1,1);
    reject(2,2,1,2);reject(3,1,1,1);drive(1);
    cache_test_geometry.x=100;cache_test_geometry.y=40;
    assert(call(3,1,0)==0);drive(3);
    cache_test_geometry.x=151;cache_test_geometry.y=83;
    assert(call(3,1,0)==0);drive(3);assert(rows==312);
    assert(call(3,1,0)==0 && call(4,1,1)==0);
    assert(call(1,0,0)==0 && cache_test_generation==2 && controller_test_phase==0);
    reject(4,1,1,1);
    fixed_flow.generation=65535;
    assert(call(2,1,0)==0 && cache_test_generation==65535);
    assert(call(1,0,0)==0 && cache_test_generation==1);reject(4,1,65535,1);
    cache_test_geometry=(struct udeks_cache_geometry){0,220,0,160};reject(2,1,1,1);
}
'''
        with tempfile.TemporaryDirectory() as name:
            work = Path(name); source = work / 'test.c'; source.write_text(harness)
            config = work / 'config.h'
            config.write_text('#include "udeks/window_cache_flow.h"\n'
                'extern struct udeks_cache_flow fixed_flow;\n'
                '#define UDEKS_CACHE_FLOW_ADDRESS (&fixed_flow)\n'
                '#define flow_test_handle cache_test_owner\n'
                '#define flow_test_generation cache_test_generation\n'
                '#define flow_test_geometry cache_test_geometry\n'
                '#define flow_test_eligible cache_test_eligible\n')
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-D__fastcall__=',
                '-DUDEKS_CACHE_FLOW_HOST_TEST', '-DUDEKS_CACHE_COMMAND_HOST_TEST',
                '-DUDEKS_CACHE_FLOW_IN_BANK', '-DUDEKS_CACHE_CONTROLLER_HOST_TEST',
                '-DUDEKS_CACHE_IMAGE_CAPACITY=2224u', '-include', str(config), '-I', str(ROOT / 'include'),
                str(source), str(ROOT / 'bench/window-cache-controller/controller.c'),
                *[str(ROOT / 'src/services/window' / n) for n in
                  ('move_cache_flow.c', 'cache_overlay.c', 'move_cache_state.c')],
                '-o', str(work / 'test')], check=True, capture_output=True)
            subprocess.run([str(work / 'test')], check=True, capture_output=True)

    def test_decoder_rejects_incomplete_pixels_rows_tickets_and_faults(self):
        for case in (0, 1):
            good = synthetic(case); decode(good, case)
            for i in (4,5,6,7,8,10,14,15,16,17,18,19,20,21,23,26,30,34,36,63,64,8095):
                bad = bytearray(good); bad[i] ^= 1
                with self.subTest(case=case, offset=i), self.assertRaises(ValueError): decode(bad, case)
        for name, fields in (('irq-leak', (15,)), ('zp-leak', (16,)), ('shell-stack', (19,21)), ('no-pending', ())):
            bad = synthetic()
            for i in fields: bad[i] = 1
            if name == 'shell-stack': bad[22] = 240
            if name == 'no-pending': bad[26] = 1; bad[30] = 0; bad[34] = 0
            negative(bad, name)
            with self.assertRaises(ValueError): decode(bad, 0)

    def test_full_linked_budget_types_row_core_and_input_hashes(self):
        directory = ROOT / 'bench/artifacts' / NAME; build = directory / 'build'
        r = json.loads((build / 'build-report.json').read_text())
        self.assertEqual(r['module_bytes'], 3977)
        self.assertEqual(r['objects']['flow']['CODE'], 637)
        self.assertEqual(r['objects']['controller']['CODE'], 209)
        self.assertEqual(r['objects']['binding']['CODE'], 241)
        self.assertEqual(r['remaining_resident_padding_before_hooks_delivery'], 261)
        self.assertEqual(r['private_stack'], [0x5250, 0x533f])
        self.assertEqual(r['stack_guard'], [0x5340, 0x534f])
        self.assertEqual(r['image'], [0x5350, 0x5bff])
        self.assertEqual(r['image_bytes'], 2224); self.assertEqual(r['image_spare'], 40)
        _, segments = parse_map((build / 'module.map').read_text())
        self.assertEqual(dict((n,(s,e)) for n,s,e in segments)['PRIVATESTATE'], (0x5220, 0x5239))
        self.assertTrue(all(e < 0x5220 for n,s,e in segments if n in ('CODE','RODATA','DATA')))
        symbols = map_exports((build / 'module.map').read_text())
        expected = {'sp':6,'sreg':8,'regsave':10,'ptr1':14,'ptr2':16,'ptr3':18,
                    'ptr4':20,'tmp1':22,'tmp2':23,'tmp3':24,'tmp4':25,'regbank':26}
        self.assertEqual({n:symbols[n][0] for n in expected}, expected)
        self.assertTrue(all(symbols[n][1] == 'RLZ' for n in expected))
        old = ROOT / 'bench/artifacts/2026-09-28-window-cache-command/build/module.bin'
        self.assertEqual((build / 'module.bin').read_bytes()[:213], old.read_bytes()[:213])
        for key, root in (('source_sha256', directory), ('linked_sha256', build), ('program_sha256', build)):
            for n, sha in r[key].items():
                self.assertEqual(hashlib.sha256((root / n).read_bytes()).hexdigest(), sha, n)

    def test_preserved_two_emulator_evidence_and_live_one_byte_faults(self):
        artifacts = ROOT / 'bench/artifacts' / NAME; results = ROOT / 'bench/results' / NAME
        build = artifacts / 'build'; r = json.loads((build / 'build-report.json').read_text())
        program = (build / 'probe-0.prg').read_bytes(); gate = (build / 'gateway.bin').read_bytes()
        for name, c in r['negative_controls'].items():
            bad = (build / f'probe-{name}.prg').read_bytes()
            self.assertEqual(len(bad), len(program))
            self.assertEqual([i for i,(a,b) in enumerate(zip(program,bad)) if a!=b], [c['offset']])
            self.assertEqual(program[c['offset']], c['before']); self.assertEqual(bad[c['offset']], c['after'])
            if name != 'no-pending':
                self.assertTrue(program.index(gate) <= c['offset'] < program.index(gate)+len(gate))
        for engine in ('1986', 'vice'):
            run = json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['program_sha256'], r['program_sha256'])
            self.assertEqual(set(run['raw_sha256']), {f'{engine}-{c}.bin' for c in CASES})
            for c in CASES:
                path = results / f'{engine}-{c}.bin'
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), run['raw_sha256'][path.name])
                value = decode(path.read_bytes(), c) if isinstance(c,int) else negative(path.read_bytes(), c)
                self.assertEqual(value, run['decoded'][str(c)])
