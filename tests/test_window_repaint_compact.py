# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_repaint_compact import SOURCE, candidate, isolated_config, library_inventory
from window_cache_manager import replace
from test_window_cache_manager import compile_run
from test_window_cache_partial_manager import transport


class WindowRepaintCompactTests(unittest.TestCase):
    def run_pair(self, harness):
        outputs = []
        with tempfile.TemporaryDirectory() as directory:
            for name, source in (('baseline', SOURCE.read_text()), ('compact', candidate(SOURCE.read_text()))):
                source = source.replace('(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))',
                                        'test_status[offset]')
                try:
                    outputs.append(compile_run(Path(directory), name,
                        '#define UDEKS_CACHE_MANAGER_HOST_TEST\n#define OPTIMIZED 1\n' + harness.replace('SOURCE', source),
                        (ROOT / 'src/services/window/move_cache_state.c',)))
                except subprocess.CalledProcessError as error:
                    self.fail(name + ': ' + error.output[-1000:].replace(b'\0', b'').decode(errors='replace'))
        self.assertEqual(outputs[0], outputs[1])

    def harness(self):
        harness = transport((ROOT / 'bench/window-cache-manager/occlusion-host.inc').read_text())
        # This oracle's owner==1 windows always have handle 1 (asserted in its
        # cases). A mock painter is not an internal owner-field reader in the
        # real OS; use that caller-owned identity for both implementations.
        return replace(harness, 'w->owner==1', 'h==1')

    def test_all_retained_occlusion_partial_paste_and_uncover_canvases_match(self):
        self.run_pair(self.harness())

    def test_sparse_slots_all_owner_bytes_drag_close_reset_and_rank_retirement(self):
        harness = self.harness().split('int main(void){', 1)[0]
        harness += r'''
static unsigned closed;
static void on_close(unsigned char h) {
 ++closed;
 assert(window_by_handle(h)==0); /* Retired before calling the client. */
}
static void snapshot(void) {
 fwrite(test_status,1,sizeof(test_status),stdout);
 fwrite(calls,1,sizeof(calls),stdout);
 fwrite(&closed,1,sizeof(closed),stdout);
 dump();
}
static void invariant(void) {
 unsigned count=0,ranks=0;
 for(unsigned h=1;h<=4;++h) {
  struct udeks_window *w=window_by_handle(h);
  if(w) {++count; assert(w->z && w->z<=active_count);
   assert(!(ranks&(1u<<w->z)));ranks|=1u<<w->z;}
 }
 assert(count==active_count);
 assert(ranks==((1u<<(count+1))-2u));
 assert((focused_handle==0)==(count==0));
}
int main(void) {
 for(unsigned owner=0;owner<256;++owner) {
  udeks_cache_init(&lease,2224);udeks_window_manager_start();memset(screen,0,sizeof(screen));content=owner%4;
  assert(!udeks_window_create(owner,2,15,0,0,64,64,0,paint,on_close));
  assert(active_count==0 && focused_handle==0);
  assert(udeks_window_destroy(1)==UDEKS_WINDOW_INVALID);
  for(unsigned h=1;h<=4;++h) {
   assert(udeks_window_create(owner,1,255,(h-1)*60,10+h*10,64,64,
    (const unsigned char *)"a z?",paint,on_close)==h);
   invariant();
  }
  assert(!udeks_window_create(owner,1,15,0,0,64,64,0,paint,0));
  assert(udeks_window_destroy(2)==0);invariant();
  assert(udeks_window_destroy(4)==0);invariant();snapshot();
  assert(udeks_window_create(owner,1,0,254,130,66,70,0,paint,0)==2);invariant();
  assert(udeks_window_image_complete(2)==0);assert(cache_phase==1);drive();
  begin_drag(2,260,135,DRAG_MOVE);drag_x=70;drag_y=80;
  finish_drag();assert(cache_phase==3);drive();invariant();snapshot();
  begin_drag(1,8,25,DRAG_RESIZE);drag_width=90;drag_height=90;
  finish_drag();invariant();snapshot();
  begin_drag(3,128,45,DRAG_MOVE);udeks_window_destroy(3);
  assert(!dragging_handle);invariant();snapshot();
  udeks_window_destroy(1);udeks_window_destroy(2);invariant();
  /* Empty top_window must not focus a free rank-zero slot. */
  assert(top_window()==0 && focused_handle==0);snapshot();
  assert(udeks_window_create(owner,1,15,0,0,64,64,0,paint,0)==1);invariant();
  udeks_window_manager_reset();invariant();
  for(unsigned h=1;h<=4;++h)assert(!window_by_handle(h));snapshot();
 }
 return 0;
}
'''
        self.run_pair(harness)

    def test_reclaim_preserves_live_empty_rank_guard_and_public_parameter_checks(self):
        source = candidate(SOURCE.read_text())
        self.assertIn('surface != UDEKS_WINDOW_SURFACE_BITMAP', source)
        self.assertIn('unsigned char owner, unsigned char surface, unsigned char flags', source)
        self.assertNotIn('unsigned char owner;', source)
        self.assertNotIn('unsigned char surface;', source)
        self.assertNotIn('unsigned char active;', source)
        top = source.split('static unsigned char top_window(void)', 1)[1].split('static unsigned char raise_window', 1)[0]
        self.assertIn('windows[index].z != 0 &&', top)
        destroy = source.split('unsigned char udeks_window_destroy', 1)[1].split('unsigned char udeks_window_repaint', 1)[0]
        self.assertLess(destroy.index('old_z = window->z;'), destroy.index('window->z = 0;'))
        self.assertLess(destroy.index('window->z = 0;'), destroy.index('close(handle);'))

    def test_new_owner_surface_readers_fail_closed(self):
        for field in ('owner', 'surface'):
            for expression in (f'window->{field}', f'windows[0].{field}'):
                with self.assertRaisesRegex(ValueError, 'lifetime changed'):
                    candidate(SOURCE.read_text() + f'\nvoid reader(void) {{ {expression}; }}\n')

    def test_all_split_outputs_are_isolated_including_panic(self):
        for name in ('8502-bootstrap.cfg', '8502-panic-probe.cfg'):
            text = (ROOT / 'cfg' / name).read_text()
            directory = ROOT / 'build/window-repaint-compact/test'
            result = isolated_config(text, directory)
            self.assertNotIn('file = "build/', result)
            self.assertEqual(text.count('file ='), result.count('file ='))
        with self.assertRaisesRegex(ValueError, 'escaped'):
            isolated_config('MEMORY { a: file = "/tmp/not-private.bin"; }', directory)

    def test_library_inventory_handles_absolute_and_relative_paths_and_rejects_empty(self):
        for name in ('none.lib', '/usr/share/cc65/lib/none.lib'):
            fixture = f'Modules list:\n{name}(add.o):\n    CODE Offs=0000 Size=000A\nSegment list:\n'
            self.assertEqual(library_inventory(fixture), {name + '(add.o)': {'CODE': 10}})
        with self.assertRaisesRegex(ValueError, 'missing linked library'):
            library_inventory('Modules list:\nSegment list:\n')


if __name__ == '__main__':
    unittest.main()
