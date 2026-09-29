# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from window_cache_command import NAME,decode,negative,reference
from placement_audit import parse_map
from gen_capability_imports import map_exports

def synthetic(case=0):
    data=bytearray(8096);data[:8]=b'CMND\x01\x02'+bytes((case,0))
    rows,calls,images=(132,543,66) if case==0 else (312,336,2)
    data[8:10]=rows.to_bytes(2,'little');data[10:12]=calls.to_bytes(2,'little')
    data[12]=1;data[14]=images;data[22]=217;data[23]=15;data[64:]=reference(case)
    return data

class WindowCacheCommandTests(unittest.TestCase):
    def test_real_command_c_atomic_rejection_single_row_and_repeated_reuse(self):
        harness=r'''
#include <assert.h>
#include <string.h>
#include "udeks/window_cache_command.h"
struct udeks_cache_lease cache_test_lease;
struct udeks_cache_row cache_test_row;
struct udeks_cache_geometry cache_test_geometry;
uint8_t cache_test_owner,cache_test_eligible,cache_test_params[9];
uint16_t cache_test_generation;
static unsigned transfers;
void udeks_cache_overlay_row(void) {++transfers;}
static unsigned command(unsigned op) {return udeks_cache_overlay_command(op);}
static void reject(unsigned op,unsigned result) {
    struct udeks_cache_lease l=cache_test_lease;
    struct udeks_cache_row r=cache_test_row;
    unsigned t=transfers;unsigned char p[9];memcpy(p,cache_test_params,9);
    assert(command(op)==result);
    assert(!memcmp(&l,&cache_test_lease,sizeof l));
    assert(!memcmp(&r,&cache_test_row,sizeof r));
    assert(!memcmp(p,cache_test_params,9) && transfers==t);
}
static void drive(unsigned mode) {
    unsigned h=cache_test_lease.geometry.height;
    unsigned x=cache_test_lease.geometry.x,y=cache_test_lease.geometry.y;
    unsigned width=cache_test_lease.geometry.width,stride=(width+7)/8;
    for(unsigned i=0;i<h;++i) {
        unsigned t=transfers,offset=((y+i)/8)*320+(y+i)%8+(x/8)*8;
        unsigned address=0x5000+i*stride;
        assert(command(4)==(0x80|(mode?0x40:0)|(i+1==h?2:(mode?3:1))));
        assert(transfers==t+1 && cache_test_lease.row==i+1);
        assert(cache_test_params[0]==(offset&255) && cache_test_params[1]==offset/256);
        assert(cache_test_params[2]==(address&255) && cache_test_params[3]==address/256);
        assert(cache_test_params[4]==stride && cache_test_params[5]==(width+x%8+7)/8);
        assert(cache_test_params[6]==x%8 && cache_test_params[8]==mode);
        assert(cache_test_params[7]==(width%8?(unsigned char)(255u<<(8-width%8)):255));
    }
    reject(4,1);assert(command(5)==0x82);
}
int main(void) {
    assert(command(0)==0x80 && cache_test_lease.capacity==3072);
    cache_test_geometry=(struct udeks_cache_geometry){7,168,7,104};
    cache_test_owner=1;cache_test_generation=65535;cache_test_eligible=0;
    reject(2,1);cache_test_eligible=1;cache_test_generation=0;reject(2,1);
    cache_test_generation=65535;cache_test_owner=0;reject(2,1);
    cache_test_owner=1;assert(command(2)==0x81);reject(3,1);reject(5,1);
    cache_test_generation=1;reject(4,1);cache_test_generation=65535;
    cache_test_owner=2;reject(4,1);reject(2,2);
    assert(command(1)==0x81);cache_test_owner=1;
    drive(0);reject(255,1);
    /* READY is read-only and dimensions/generation/ownership are mandatory. */
    cache_test_owner=0;reject(5,1);cache_test_owner=1;
    cache_test_generation=0;reject(5,1);cache_test_generation=1;reject(5,1);
    cache_test_generation=65535;cache_test_geometry.width++;reject(5,1);reject(3,1);
    cache_test_geometry.width--;cache_test_geometry.x=319;reject(3,1);
    cache_test_geometry.x=100;cache_test_geometry.y=40;
    assert(command(3)==0x83);drive(1);
    cache_test_geometry.x=151;cache_test_geometry.y=83;
    assert(command(3)==0x83);drive(1);assert(transfers==312);
    /* Invalidate cancels both capture and paste before another transfer. */
    assert(command(1)==0x80);reject(4,1);reject(5,1);
    cache_test_generation=1;assert(command(2)==0x81);assert(command(4)==0x81);
    assert(command(1)==0x80);reject(4,1);
    cache_test_geometry=(struct udeks_cache_geometry){0,256,0,96};
    assert(command(2)==0x81);drive(0);
    cache_test_geometry.x=1;assert(command(3)==0x83);assert(command(4)==0xc3);
    cache_test_owner=0;assert(command(1)==0x80);cache_test_owner=1;reject(4,1);
    cache_test_geometry.height=97;reject(2,1);
}
'''
        with tempfile.TemporaryDirectory() as name:
            work=Path(name);path=work / 'test.c';path.write_text(harness)
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-D__fastcall__=',
                '-DUDEKS_CACHE_COMMAND_HOST_TEST','-I',str(ROOT / 'include'),str(path),
                str(ROOT / 'src/services/window/cache_overlay.c'),
                str(ROOT / 'src/services/window/move_cache_state.c'),'-o',str(work / 'test')],
                check=True,capture_output=True)
            subprocess.run([str(work / 'test')],check=True,capture_output=True)

    def test_decoder_and_fault_controls_require_exact_work_and_full_pixels(self):
        for case in (0,1):
            good=synthetic(case);decode(good,case)
            for i in (4,5,6,7,8,10,14,15,16,17,18,19,20,21,23,26,63,64,8095):
                bad=bytearray(good);bad[i]^=1
                with self.subTest(case=case,offset=i),self.assertRaises(ValueError):decode(bad,case)
        for name,fields in (('irq-leak',(15,)),('zp-leak',(16,)),('shell-stack',(19,21))):
            bad=synthetic()
            for i in fields:bad[i]=1
            if name=='shell-stack':bad[22]=0xf0
            self.assertEqual(negative(bad,name)['detected_fields'],list(fields))
            with self.assertRaises(ValueError):decode(bad,0)
            for i in fields:
                absent=bytearray(bad);absent[i]=0
                with self.assertRaises(ValueError):negative(absent,name)

    def test_combined_link_budget_runtime_types_and_immutable_row_core(self):
        directory=ROOT / 'bench/artifacts' / NAME;build=directory / 'build'
        report=json.loads((build / 'build-report.json').read_text())
        self.assertEqual(report['module_bytes'],3116)
        self.assertEqual(report['command_object']['CODE'],517)
        self.assertEqual(report['binding_object']['CODE'],241)
        self.assertEqual(report['gateway_bytes'],217)
        self.assertEqual(report['remaining_resident_padding'],275)
        self.assertEqual(report['private_stack'],[0x4f00,0x4fef])
        self.assertEqual(report['image'],[0x5000,0x5bff])
        _,segments=parse_map((build / 'module.map').read_text())
        by_name={n:(s,e) for n,s,e in segments}
        self.assertEqual(by_name['ZEROPAGE'],(6,31))
        self.assertEqual(by_name['PRIVATESTATE'],(0x4ee0,0x4ef5))
        self.assertLess(by_name['CODE'][1],0x4ee0)
        symbols=map_exports((build / 'module.map').read_text())
        expected={'sp':6,'sreg':8,'regsave':10,'ptr1':14,'ptr2':16,'ptr3':18,
                  'ptr4':20,'tmp1':22,'tmp2':23,'tmp3':24,'tmp4':25,'regbank':26}
        self.assertEqual({n:symbols[n][0] for n in expected},expected)
        row=ROOT / 'bench/artifacts/2026-09-28-window-cache-overlay/build/core.bin'
        self.assertEqual((build / 'module.bin').read_bytes()[:213],row.read_bytes())
        for name,sha in report['linked_sha256'].items():
            self.assertEqual(hashlib.sha256((build / name).read_bytes()).hexdigest(),sha,name)
        for name,sha in report['source_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)

    def test_preserved_runs_bind_all_programs_and_single_byte_faults(self):
        artifacts=ROOT / 'bench/artifacts' / NAME;results=ROOT / 'bench/results' / NAME
        build=artifacts / 'build';report=json.loads((build / 'build-report.json').read_text())
        program=(build / 'probe-0.prg').read_bytes();gate=(build / 'gateway.bin').read_bytes()
        self.assertEqual(program.count(gate),1)
        for name,c in report['negative_controls'].items():
            bad=(build / f'probe-{name}.prg').read_bytes()
            self.assertEqual([i for i,(a,b) in enumerate(zip(program,bad)) if a!=b],[c['offset']])
            self.assertEqual(len(program),len(bad))
            self.assertTrue(program.index(gate)<=c['offset']<program.index(gate)+len(gate))
        for name,sha in report['program_sha256'].items():
            self.assertEqual(hashlib.sha256((build / name).read_bytes()).hexdigest(),sha)
        for engine in ('1986','vice'):
            run=json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['program_sha256'],report['program_sha256'])
            for c in (0,1,'irq-leak','zp-leak','shell-stack'):
                path=results / f'{engine}-{c}.bin'
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),run['raw_sha256'][path.name])
                result=decode(path.read_bytes(),c) if isinstance(c,int) else negative(path.read_bytes(),c)
                self.assertEqual(result,run['decoded'][str(c)])
