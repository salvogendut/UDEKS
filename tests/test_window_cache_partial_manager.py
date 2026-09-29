# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from window_cache_partial_manager import candidate
from window_cache_occlusion import occluded
from window_cache_manager import BASE,replace
from test_window_cache_manager import compile_run


def transport(harness):
    harness=replace(harness,'static struct udeks_cache_lease lease;', '''unsigned char manager_partial_first, manager_partial_end;
unsigned int manager_partial_width;
static unsigned char partial_end;
static unsigned int partial_width;
static struct udeks_cache_lease lease;''')
    harness=replace(harness,' default:assert(0);', ''' case 6:
   assert(manager_partial_first < manager_partial_end && manager_partial_end <= manager_test_geometry.height);
   assert(manager_partial_width && manager_partial_width <= manager_test_geometry.width);
   result=udeks_cache_paste_begin(&lease,manager_test_owner,1,&manager_test_geometry);
   assert(result==0);++paste_requests;
   lease.row=manager_partial_first;partial_end=manager_partial_end;partial_width=manager_partial_width;
   break;
 default:assert(0);''')
    harness=replace(harness,'   for(unsigned x=0;x<lease.geometry.width;++x){',
        '   for(unsigned x=0;x<(lease.phase==3 && partial_width ? partial_width : lease.geometry.width);++x){')
    harness=replace(harness,'   result=udeks_cache_commit_row(&lease,lease.owner,1,y);', '''   result=udeks_cache_commit_row(&lease,lease.owner,1,y);
   if(partial_width && row.mode && lease.row==partial_end) {
     lease.phase=2;partial_width=0;
   }''')
    harness=replace(harness,' struct udeks_window *w=window_by_handle(h);++calls[h];', ''' struct udeks_window *w=window_by_handle(h);++calls[h];
 /* Any callback may use the shared VIC parameter area. The manager must
  * marshal the final prefix only after composition and its callbacks. */
 manager_partial_first=255;manager_partial_end=0;manager_partial_width=65535;''')
    return harness


class PartialManagerTests(unittest.TestCase):
    def test_full_canvases_uncovering_and_callback_workspace_clobber(self):
        harness=(ROOT/'bench/window-cache-manager/occlusion-host.inc').read_text()
        with tempfile.TemporaryDirectory() as directory:
            traces=[]
            for name,transform in (('reference',occluded),('partial',candidate)):
                source=transform(BASE.read_text()).replace(
                    '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))','test_status[offset]')
                code='#define UDEKS_CACHE_MANAGER_HOST_TEST\n#define OPTIMIZED 1\n'
                traces.append(compile_run(Path(directory),name,
                    code+transport(harness).replace('SOURCE',source),
                    (ROOT/'src/services/window/move_cache_state.c',)))
            self.assertEqual(traces[0],traces[1])

    def test_no_placement_or_poll_budget_expansion(self):
        source=candidate(BASE.read_text())
        self.assertIn('unsigned char budget = 4;',source)
        self.assertIn('else if (cache_request(handle, 6)',source)
        self.assertLess(source.index('compose_damage(handle);'),
            source.index('paste = set_damage_intersection(cached->x'))
        self.assertEqual(source.count('#pragma bss-name'),BASE.read_text().count('#pragma bss-name'))


if __name__=='__main__':unittest.main()
