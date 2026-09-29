# SPDX-License-Identifier: GPL-3.0-or-later
"""Check actual prototype C, independent pixel references, and machine evidence."""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_bench import decode, decode_record, reference

HARNESS = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
static unsigned char shadow[8000], stage[256], bank[65536], dirty[32];
static unsigned int address;
static unsigned char count;
SOURCE
void cache_transfer(unsigned char mode) {
    if (mode==2) {memcpy(stage,bank+0x4000,256);return;}
    assert(count && count<=40 && address>=0x4200 && address+count<=0x5c00);
    if (mode==0) memcpy(bank+address,stage,count);
    else {assert(mode==1);memcpy(stage,bank+address,count);}
}
static unsigned index_at(unsigned x,unsigned y) {
    return (y/8)*320+(x/8)*8+y%8;
}
int main(void) {
    static unsigned char original[8000], expected[8000], expected_dirty[32];
    unsigned geometry[][2]={{168,104},{220,160},{17,11},{1,1},{63,39},{320,166}};
    for(unsigned g=0;g<6;++g) for(unsigned sa=0;sa<8;++sa) for(unsigned da=0;da<8;++da) {
        unsigned w=geometry[g][0],h=geometry[g][1];
        unsigned sx=w==320?0:sa, sy=200-h, dx=w==320?0:da, dy=0;
        for(unsigned i=0;i<8000;++i) original[i]=shadow[i]=(unsigned char)(i*13+sa*17+g);
        memset(dirty,0,sizeof dirty);memset(expected_dirty,0,sizeof expected_dirty);
        memset(bank,0xa5,sizeof bank);
        for(unsigned i=0;i<256;++i) stage[i]=bank[0x4000+i]=(unsigned char)(i*3+1);
        assert(cache_capture(sx,sy,w,h));
        assert(!memcmp(stage,bank+0x4000,256));
        unsigned end=0x4200+((w+7)/8)*h;
        for(unsigned i=0;i<65536;++i)
            if(!(i>=0x4000 && i<0x4100) && !(i>=0x4200 && i<end)) assert(bank[i]==0xa5);
        for(unsigned i=0;i<8000;++i) expected[i]=shadow[i]=(unsigned char)(i*31+da*19+g);
        assert(cache_paste(dx,dy));
        for(unsigned y=0;y<h;++y) for(unsigned x=0;x<w;++x) {
            unsigned s=index_at(sx+x,sy+y),t=index_at(dx+x,dy+y);
            unsigned char mask=128>>((dx+x)%8);
            if(original[s] & (128>>((sx+x)%8))) expected[t]|=mask;
            else expected[t]&=(unsigned char)~mask;
            expected_dirty[t>>8]=1;
        }
        assert(!memcmp(shadow,expected,8000));
        assert(!memcmp(dirty,expected_dirty,32));
        assert(!memcmp(stage,bank+0x4000,256));
        assert(!cache_paste(320,200));
        assert(!memcmp(shadow,expected,8000));
        assert(!cache_capture(0,0,320,200));
        assert(!cache_paste(0,0)); /* failed capture invalidates the old lease */
        assert(!memcmp(shadow,expected,8000));
        assert(!cache_capture(0,0,0,1));
        assert(!cache_capture(0,0,321,1));
        assert(!cache_capture(0,0,1,0));
        assert(!cache_capture(0,0,1,201));
        assert(!cache_capture(320,0,1,1));
        assert(!cache_capture(0,200,1,1));
    }
}
'''


class WindowCacheBenchTests(unittest.TestCase):
    def test_real_c_all_alignments_masking_capacity_and_rejection(self):
        source = (ROOT / 'bench/window-cache/cache.c').read_text()
        for name, value in {'SHADOW': 'shadow', 'STAGE': 'stage', 'ADDRESS': 'address',
                            'COUNT': 'count', 'DIRTY': 'dirty'}.items():
            source, changed = re.subn(r'^#define ' + name + r' .*$',
                                      '#define ' + name + ' ' + value, source, flags=re.M)
            self.assertEqual(changed, 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.c').write_text(HARNESS.replace('SOURCE', source))
            subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-D__fastcall__=', '-I', str(ROOT / 'bench/window-cache'),
                            str(path / 'test.c'), '-o', str(path / 'test')],
                           check=True, capture_output=True)
            subprocess.run([str(path / 'test')], check=True, capture_output=True)

    def test_decoder_rejects_false_passes(self):
        for case in range(11):
            block = bytearray(64) + bytearray(reference(case))
            block[:8] = b'WCAC\x01\x02' + bytes((case, 0))
            block[8:12] = block[22:26] = (200).to_bytes(4, 'little')
            block[18:22] = (100).to_bytes(4, 'little')
            block[12:18] = b'\x5a\xa5\x3e\x01\x01\xc3'
            self.assertEqual(decode_record(block, case)['total_ticks'], 300)
            for offset in (0, 4, 5, 6, 7, 8, 12, 13, 14, 15, 16, 17, 26, 63, 64, 8064):
                damaged = block[:]
                damaged[offset] ^= 1
                with self.assertRaises(ValueError, msg=(case, offset)):
                    decode_record(damaged, case)
            block[18:22] = bytes(4)
            with self.assertRaises(ValueError):
                decode_record(block, case)
            with self.assertRaises(ValueError):
                decode_record(block[:-1], case)

    def test_preserved_machine_roundtrips_and_placement(self):
        name = '2026-09-28-window-cache-transfer'
        results = ROOT / 'bench/results' / name
        report = decode(results / 'raw')
        self.assertEqual(report, json.loads((results / 'report.json').read_text()))
        artifact = ROOT / 'bench/artifacts' / name
        build = json.loads((artifact / 'build-report.json').read_text())
        self.assertEqual(build['gateway'], {'size': 99, 'run': 0xF68A, 'end_inclusive': 0xF6EC})
        self.assertEqual(build['cache_object']['CODE'], 1113)
        self.assertEqual(build['cache_object']['BSS'], 30)
        self.assertEqual(build['transfer_object']['CODE'], 130)
        for source, digest in build['sources_sha256'].items():
            self.assertEqual(hashlib.sha256((artifact / source).read_bytes()).hexdigest(), digest)
        self.assertEqual(len(build['program_sha256']), 11)
        for program, digest in build['program_sha256'].items():
            self.assertEqual(hashlib.sha256((artifact / program).read_bytes()).hexdigest(), digest)
        for directory in (results, artifact):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                digest, filename = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
                                 digest, filename)
        self.assertEqual(len(report['cases']), 11)


if __name__ == '__main__':
    unittest.main()
