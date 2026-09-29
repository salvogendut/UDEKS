# SPDX-License-Identifier: GPL-3.0-or-later
"""Private clipping rewrite must preserve valid manager geometry and effects."""
from pathlib import Path
import sys
import tempfile
import unittest

from test_window_cache_manager import compile_run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_repaint_intersection import REUSE_BODY, SOURCE  # noqa: E402

HARNESS = r'''
#include <assert.h>
#include <stdio.h>
static unsigned int damage_left, damage_right, partial_width;
static unsigned char damage_top, damage_bottom, partial_first, partial_end;
static unsigned int clip_x, clip_y, clip_width, clip_height, clip_calls;
#define CACHE_PARTIAL_FIRST partial_first
#define CACHE_PARTIAL_END partial_end
#define CACHE_PARTIAL_WIDTH partial_width
static void udeks_vic_bitmap_set_clip(int x, int y, int width, int height) {
    clip_x=x; clip_y=y; clip_width=width; clip_height=height; ++clip_calls;
}
FUNCTION
int main(void) {
    unsigned int i, x, width, dl, dr, left, right;
    unsigned char y, height, dt, db, top, bottom, expected;
    for (i=0; i<4096u; ++i) {
        x=(i*17u)%321u; y=(unsigned char)((i*13u)%201u);
        width=(i*29u)%(321u-x); height=(unsigned char)((i*19u)%(201u-y));
        dl=(i*31u)%321u; dr=dl+(i*7u)%(321u-dl);
        dt=(unsigned char)((i*23u)%201u);
        db=(unsigned char)(dt+(i*11u)%(201u-dt));
        damage_left=dl; damage_right=dr; damage_top=dt; damage_bottom=db;
        left=x>dl?x:dl; right=x+width<dr?x+width:dr;
        top=y>dt?y:dt; bottom=y+height<db?y+height:db;
        expected=(unsigned char)(left<right && top<bottom);
        partial_first=0xA5;partial_end=0x5A;partial_width=0xBEEF;
        clip_x=clip_y=clip_width=clip_height=0xBEEF;clip_calls=0;
        assert(set_damage_intersection(x,y,width,height)==expected);
        if (expected) {
            assert(clip_calls==1 && clip_x==left && clip_y==top);
            assert(clip_width==right-left && clip_height==bottom-top);
            assert(partial_first==top-y && partial_end==bottom-y);
            assert(partial_width==right-x);
        } else {
            assert(clip_calls==0 && partial_first==0xA5 && partial_end==0x5A);
            assert(partial_width==0xBEEF);
        }
    }
    puts("4096 clipping cases OK"); return 0;
}
'''


class RepaintIntersectionTests(unittest.TestCase):
    def test_original_and_reuse_variant_match_independent_clip_oracle(self):
        source = SOURCE.read_text()
        marker = 'static unsigned char set_damage_intersection('
        start = source.index(marker)
        end = source.index('\n}', start) + 2
        original = source[start:end]
        candidate = REUSE_BODY.replace(
            '    unsigned int left;\n    unsigned char top;',
            '    register unsigned int left;\n    register unsigned char top;')
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for label, body in (('original', original), ('candidate', candidate)):
                output = compile_run(work, label, HARNESS.replace('FUNCTION', body))
                self.assertEqual(output, b'4096 clipping cases OK\n')


if __name__ == '__main__':
    unittest.main()
