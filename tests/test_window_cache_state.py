# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class WindowCacheStateTests(unittest.TestCase):
    def test_real_c_policy_geometry_atomicity_generations_and_continuations(self):
        harness=r'''
#include <assert.h>
#include <string.h>
#include "udeks/window_cache_state.h"
static struct udeks_cache_lease lease, before;
static struct udeks_cache_row row, untouched;
static void same(void) {assert(!memcmp(&lease,&before,sizeof lease));}
static void invalid_capture(unsigned owner,unsigned gen,
        struct udeks_cache_geometry g,unsigned eligible) {
    before=lease;
    assert(udeks_cache_capture_begin(&lease,owner,gen,&g,eligible)==UDEKS_CACHE_INVALID);
    same();
}
static void drive(unsigned owner,unsigned generation,unsigned mode) {
    unsigned height=lease.geometry.height,width=lease.geometry.width;
    unsigned stride=(width+7)/8;
    for(unsigned i=0;i<height;++i) {
        before=lease;
        assert(udeks_cache_prepare_row(&lease,owner,generation,&row)==UDEKS_CACHE_OK);
        same();
        unsigned y=lease.geometry.y+i,x=lease.geometry.x;
        assert(row.shadow_offset==(y/8)*320+(y%8)+(x/8)*8);
        assert(row.image_offset==i*stride);
        assert(row.stride==stride);
        assert(row.raw_count==(width+x%8+7)/8);
        assert(row.shift==x%8 && row.mode==mode);
        assert(row.last_mask==(width%8?(unsigned char)(255u<<(8-width%8)):255));
        assert(row.image_offset+stride<=lease.capacity);
        assert(row.shadow_offset+(row.raw_count-1)*8<8000);
        assert(udeks_cache_commit_row(&lease,owner,generation,i+1)==UDEKS_CACHE_INVALID);same();
        assert(udeks_cache_commit_row(&lease,owner,generation,i)==UDEKS_CACHE_OK);
        assert(lease.row==i+1);
        assert(lease.phase==(i+1==height?UDEKS_CACHE_READY:
                    (mode?UDEKS_CACHE_PASTING:UDEKS_CACHE_CAPTURING)));
    }
    before=lease;memset(&row,0xa5,sizeof row);untouched=row;
    assert(udeks_cache_prepare_row(&lease,owner,generation,&row)==UDEKS_CACHE_INVALID);
    same();assert(!memcmp(&row,&untouched,sizeof row));
    assert(udeks_cache_commit_row(&lease,owner,generation,height-1)==UDEKS_CACHE_INVALID);same();
}
int main(void) {
    struct udeks_cache_geometry g={7,168,17,104},dest;
    memset(&lease,0xa5,sizeof lease);udeks_cache_init(&lease,6144);
    assert(lease.phase==UDEKS_CACHE_EMPTY && lease.owner==0 && lease.capacity==6144);
    for(unsigned owner=0;owner<7;++owner) {
        if(owner>=1 && owner<=4)continue;
        invalid_capture(owner,1,g,1);
    }
    invalid_capture(1,0,g,1);invalid_capture(1,1,g,0);invalid_capture(1,1,g,2);
    for(unsigned kind=0;kind<10;++kind) {
        dest=g;
        switch(kind) {
        case 0:dest.width=0;break;case 1:dest.width=321;break;
        case 2:dest.width=65535;break;case 3:dest.height=0;break;
        case 4:dest.height=201;break;case 5:dest.x=65535;break;
        case 6:dest.y=255;break;case 7:dest.x=320;break;
        case 8:dest.y=199;break;case 9:dest.width=320;dest.height=200;dest.x=dest.y=0;break;
        }
        invalid_capture(1,1,dest,1);
    }
    assert(udeks_cache_capture_begin(&lease,1,65535,&g,1)==UDEKS_CACHE_OK);
    before=lease;
    assert(udeks_cache_capture_begin(&lease,2,1,&g,1)==UDEKS_CACHE_BUSY);same();
    memset(&row,0xa5,sizeof row);untouched=row;
    assert(udeks_cache_prepare_row(&lease,2,65535,&row)==UDEKS_CACHE_INVALID);same();
    assert(udeks_cache_prepare_row(&lease,1,1,&row)==UDEKS_CACHE_INVALID);same();
    assert(!memcmp(&row,&untouched,sizeof row));
    assert(udeks_cache_paste_begin(&lease,1,65535,&g)==UDEKS_CACHE_INVALID);same();
    drive(1,65535,0);
    before=lease;dest=g;dest.x=100;dest.y=40;
    assert(udeks_cache_paste_begin(&lease,2,65535,&dest)==UDEKS_CACHE_INVALID);same();
    assert(udeks_cache_paste_begin(&lease,1,1,&dest)==UDEKS_CACHE_INVALID);same();
    dest.width++;
    assert(udeks_cache_paste_begin(&lease,1,65535,&dest)==UDEKS_CACHE_INVALID);same();
    dest=g;dest.y=150;
    assert(udeks_cache_paste_begin(&lease,1,65535,&dest)==UDEKS_CACHE_INVALID);same();
    dest=g;dest.x=100;dest.y=40;
    assert(udeks_cache_paste_begin(&lease,1,65535,&dest)==UDEKS_CACHE_OK);
    drive(1,65535,1);
    before=lease;udeks_cache_invalidate(&lease,2);same();
    udeks_cache_invalidate(&lease,1);
    assert(lease.phase==UDEKS_CACHE_EMPTY && lease.generation==0 && lease.capacity==6144);
    before=lease;
    assert(udeks_cache_commit_row(&lease,1,65535,103)==UDEKS_CACHE_INVALID);same();
    assert(udeks_cache_capture_begin(&lease,1,1,&g,1)==UDEKS_CACHE_OK);
    assert(udeks_cache_commit_row(&lease,1,65535,0)==UDEKS_CACHE_INVALID);
    udeks_cache_invalidate(&lease,0);assert(lease.phase==UDEKS_CACHE_EMPTY);
    /* Exhaustive positions on all bit/row phases; nonbyte and maximal widths,
       exact capacity boundaries, and a reduced future module-image capacity. */
    unsigned widths[]={1,7,8,9,17,168,220,319,320};
    unsigned caps[]={3584,5120,6144};
    for(unsigned c=0;c<3;++c)for(unsigned w=0;w<9;++w)
      for(unsigned sa=0;sa<8;++sa)for(unsigned da=0;da<8;++da) {
        g.x=sa;g.y=sa;g.width=widths[w];g.height=8;
        if(g.x+g.width>320)g.x=320-g.width;
        udeks_cache_init(&lease,caps[c]);
        assert(udeks_cache_capture_begin(&lease,1,1,&g,1)==UDEKS_CACHE_OK);drive(1,1,0);
        dest=g;dest.x=da;dest.y=190;
        if(dest.x+dest.width>320)dest.x=320-dest.width;
        assert(udeks_cache_paste_begin(&lease,1,1,&dest)==UDEKS_CACHE_OK);drive(1,1,1);
      }
    udeks_cache_init(&lease,6144);g.x=g.y=0;g.width=320;g.height=153;
    assert(udeks_cache_capture_begin(&lease,4,1,&g,1)==UDEKS_CACHE_OK);drive(4,1,0);
    g.height=154;invalid_capture(4,1,g,1);
    udeks_cache_init(&lease,3584);g.width=256;g.height=112;
    assert(udeks_cache_capture_begin(&lease,4,1,&g,1)==UDEKS_CACHE_OK);drive(4,1,0);
    g.height=113;invalid_capture(4,1,g,1);
}
'''
        with tempfile.TemporaryDirectory() as name:
            work=Path(name);path=work / 'test.c';path.write_text(harness)
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-I',str(ROOT / 'include'),
                str(path),str(ROOT / 'src/services/window/move_cache_state.c'),'-o',str(work / 'test')],
                check=True,capture_output=True)
            subprocess.run([str(work / 'test')],check=True,capture_output=True)

    def test_policy_is_not_linked_into_kernel_or_hardware_coupled(self):
        source=(ROOT / 'src/services/window/move_cache_state.c').read_text()
        make=(ROOT / 'Makefile').read_text()
        self.assertNotIn('move_cache_state.o',make)
        self.assertNotIn('volatile',source)
        self.assertNotIn('udeks_vic_',source)
        self.assertNotIn('udeks_window_',source)
