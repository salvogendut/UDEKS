# SPDX-License-Identifier: GPL-3.0-or-later
import ast
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class WindowClick(unittest.TestCase):
    def test_client_click_ownership_once_only_and_fixed_geometry(self):
        # Reuse the real manager's existing drawing/input stubs.
        tree=ast.parse((ROOT/'tests/test_window_manager_budget.py').read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)
                    and n.name=='test_real_c_manager_matches_baseline_geometry_state_and_all_drawing_calls')
        harness=next(ast.literal_eval(n.value) for n in method.body if isinstance(n,ast.Assign)
                     and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='harness')
        harness='#include <assert.h>\n'+harness.split('int main(void)')[0]+r"""
int main(void) {
    udeks_window_manager_start();
    unsigned h=udeks_window_create(3,1,2|4|16,108,30,104,133,0,paint,closed);
    assert(h && !(windows[h-1].flags & UDEKS_WINDOW_FLAG_RESIZABLE));
    assert(!udeks_window_take_click(h));
    px=108+12+15; py=30+40+41; buttons=1;
    udeks_window_manager_poll();
    assert(!udeks_window_take_click(0));
    assert(!udeks_window_take_click(h+1));
    const struct udeks_window_click *event=udeks_window_take_click(h);
    assert(event && event->x==15 && event->y==41);
    assert(!udeks_window_take_click(h));
    udeks_window_manager_poll();assert(!udeks_window_take_click(h)); /* held */
    buttons=0;udeks_window_manager_poll();
    buttons=1;udeks_window_manager_poll();
    udeks_window_destroy(h);assert(!udeks_window_take_click(h));
    h=udeks_window_create(3,1,2|4|16,108,30,104,133,0,paint,closed);
    assert(!udeks_window_take_click(h)); /* recycled handle */
    buttons=0;udeks_window_manager_poll();
    px=108+12+15;py=30+40+5;buttons=1;udeks_window_manager_poll();
    assert(dragging_handle==h && !udeks_window_take_click(h));
    buttons=0;udeks_window_manager_poll();
    assert(!dragging_handle && !udeks_window_take_click(h));
    udeks_window_manager_reset();assert(!udeks_window_take_click(h));
    return 0;
}
"""
        source=(ROOT/'src/services/window/window_manager.c').read_text().replace(
            '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))','test_status[offset]')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'click.c';binary=path.with_suffix('')
            path.write_text(harness.replace('SOURCE',source))
            subprocess.run(['cc','-std=c99','-D__fastcall__=','-Wno-unknown-pragmas',
                            '-I',str(ROOT/'include'),str(path),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],stdout=subprocess.DEVNULL,check=True)

    def test_append_only_versioned_click_entry(self):
        source=(ROOT/'src/8502/app_gateway.s').read_text()
        helper=(ROOT/'user/lib/window_click.s').read_text()
        self.assertIn('.byte $00, $04',source)
        self.assertIn('.addr _udeks_window_image_complete\n        .addr _udeks_window_take_click',source)
        self.assertIn('cmp #4',helper)
        self.assertIn('jmp ($cf5a)',helper)
        self.assertNotIn('incsp',helper)  # fastcall handle; no stacked arguments
