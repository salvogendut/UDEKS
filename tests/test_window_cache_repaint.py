# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from window_cache_repaint import PREFIX,tiled,measurements
from window_cache_manager import BASE,replace
from test_window_cache_manager import compile_run


class WindowCacheRepaintTests(unittest.TestCase):
    def test_four_row_bound_and_exact_tile_flush_for_every_y_alignment(self):
        tree=ast.parse((ROOT / 'tests/test_window_cache_manager.py').read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and
                    n.name=='test_bounded_capture_move_repeated_paste_and_invalidation_fallback')
        harness=next(ast.literal_eval(n.value) for n in method.body if isinstance(n,ast.Assign)
                     and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='harness')
        harness=harness.replace('static unsigned captures,pastes,rows,paints;',
            'unsigned char manager_test_row_offset;\nstatic unsigned captures,pastes,rows,paints,commits;')
        harness=harness.replace('void udeks_vic_bitmap_commit(void){}',
                                'void udeks_vic_bitmap_commit(void){++commits;}')
        harness=replace(harness,' if(!result)cache_phase=lease.phase;return result;',
            ' if(!result){cache_phase=lease.phase;manager_test_row_offset=(lease.geometry.y+lease.row-1)&7;}return result;')
        start=harness.index('static void drive(void) {');end=harness.index('int main(void)',start)
        harness=harness[:start]+'''static void drive(void) {
 while(cache_phase==1 || cache_phase==3) {
   unsigned before=rows;udeks_window_manager_poll();assert(rows>before && rows-before<=4);
 } assert(cache_phase==2);
}
'''+harness[end:]
        # Test every starting scanline and a final partial physical band, while
        # retaining the original lifecycle/invalidation/oversize regressions.
        harness=harness.replace(' udeks_window_manager_reset();assert(cache_phase==0);', '''
 udeks_window_manager_reset();assert(cache_phase==0);
 for(unsigned y=0;y<8;++y) {
   unsigned h=udeks_window_create(2,1,15,20,y,168,104,0,paint,0);
   udeks_window_image_complete(h);drive();
   begin_drag(h,28,y+5,DRAG_MOVE);drag_y=y;finish_drag();
   unsigned before=commits;drive();
   assert(commits-before==(y?14:13));
   udeks_window_manager_reset();
 }
''')
        source=tiled(BASE.read_text()).replace(
            '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))','test_status[offset]')
        with tempfile.TemporaryDirectory() as name:
            compile_run(Path(name),'tiled','#define UDEKS_CACHE_MANAGER_HOST_TEST\n'+harness.replace('SOURCE',source),
                        (ROOT / 'src/services/window/move_cache_state.c',))

    def test_no_new_state_and_final_failure_flush_is_not_suppressed(self):
        text=tiled(BASE.read_text())
        self.assertIn('unsigned char budget = 4;',text)
        self.assertIn('(cache_phase != UDEKS_CACHE_PASTING || (CACHE_ROW_OFFSET & 7u) == 7u)',text)
        self.assertIn('volatile unsigned char *)0xF780u',text)
        self.assertNotIn('budget = 8',text)

    def test_preserved_comparison_uses_exact_bound_logs_and_both_formats(self):
        report=json.loads((ROOT / 'bench/results' / (PREFIX+'-tiled') / 'comparison.json').read_text())
        for variant in ('baseline','tiled'):
            artifact=ROOT / 'bench/artifacts' / (PREFIX+'-'+variant)
            result=ROOT / 'bench/results' / (PREFIX+'-'+variant)
            build=json.loads((artifact / 'build/report.json').read_text())
            self.assertEqual(build['remaining_padding'],159 if variant=='baseline' else 127)
            self.assertEqual(build['manager_sizes']['HIGHBSS'],88)
            self.assertEqual(build['segments']['VICSHADOW'],{'start':0xa1e0,'end':0xc11f,'size':8000})
            for engine in ('1986','vice'):
                binding=json.loads((result / (engine+'-run.json')).read_text())
                self.assertEqual(set(binding['results']),{'d71','d64'})
                self.assertEqual(binding['report_sha256'],hashlib.sha256((artifact / 'build/report.json').read_bytes()).hexdigest())
            for fmt in ('d71','d64'):
                log=result / f'1986-{fmt}.log'
                value=measurements(log.read_text())
                self.assertEqual(value,report['values'][variant][fmt])
                key=f'build/window-cache-repaint/{variant}/1986-{fmt}.log'
                self.assertEqual(hashlib.sha256(log.read_bytes()).hexdigest(),report['inputs_sha256'][key])
                self.assertIn('PASS: live cached moves, full pixels, fallback, cancellation and restart',log.read_text())
        for fmt in ('d71','d64'):
            a,b=report['values']['baseline'][fmt],report['values']['tiled'][fmt]
            for key in ('median_paste_frames','median_total_frames','median_paste_page_copies','median_paste_copy_cycles','cancel_frames'):
                self.assertLess(b[key],a[key])

    def test_failure_proves_raster_target_and_same_size_one_byte_kernel_fix(self):
        result=ROOT / 'bench/results' / (PREFIX+'-tiled') / 'failure'
        self.assertEqual(json.loads((result / 'state.json').read_text()),{
            'irq_target':482,'raster':0,'sampler_phase':1,'keyboard_matrix_row0':2,'physical_return_down':0})
        artifact=ROOT / 'bench/artifacts' / (PREFIX+'-tiled')
        fixed=artifact / 'inputs/build/window-cache-repaint/tiled/repo/build/8502/udeks-8502.bin'
        old=(result / 'udeks-8502.bin').read_bytes();new=fixed.read_bytes()
        self.assertEqual(len(old),len(new))
        diffs=[(a,b) for a,b in zip(old,new) if a!=b]
        self.assertEqual(diffs,[(0xcf,0x4f)])
        for line in (result / 'SHA256SUMS').read_text().splitlines():
            sha,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((result / name).read_bytes()).hexdigest(),sha)

    def test_preserved_manifests_and_inputs_exclude_rom_snapshots(self):
        for variant in ('baseline','tiled'):
            for kind in ('artifacts','results'):
                directory=ROOT / 'bench' / kind / (PREFIX+'-'+variant)
                self.assertFalse(list(directory.rglob('*.vsf')))
                for line in (directory / 'SHA256SUMS').read_text().splitlines():
                    sha,name=line.split('  ',1)
                    self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)


if __name__=='__main__':unittest.main()
