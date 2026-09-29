# SPDX-License-Identifier: GPL-3.0-or-later
"""Both window managers reject 16-bit wrapping create coordinates."""
import ast
from pathlib import Path
import tempfile
import unittest

from test_window_cache_manager import compile_run

ROOT = Path(__file__).resolve().parents[1]
GUARD = 'x > UDEKS_VIC_WIDTH || width > UDEKS_VIC_WIDTH - x ||'
CASES = r'''
static void rejected(unsigned x, unsigned char y, unsigned w, unsigned char h) {
    unsigned char before[32];
    memcpy(before, test_status, sizeof(before));
    assert(udeks_window_create(1,1,15,x,y,w,h,0,0,0) == UDEKS_WINDOW_NONE);
    assert(active_count == 0 && focused_handle == 0);
    assert(memcmp(before, test_status, sizeof(before)) == 0);
    assert(window_by_handle(1) == 0);
}
int main(void) {
    assert((uint16_t)(65520u + 16u) <= 320u); /* Old cc65 sum wraps to 0. */
    assert((uint16_t)(65535u + 16u) <= 320u); /* Old cc65 sum wraps to 15. */
    udeks_window_manager_start();
    rejected(65520u, 10, 16u, 20u);
    rejected(65535u, 10, 16u, 20u);
    rejected(1u, 10, 65535u, 20u);
    rejected(320u, 10, 16u, 20u);
    rejected(305u, 10, 16u, 20u);
    rejected(0u, 181u, 16u, 20u);
    assert(udeks_window_create(1,1,15,304u,180u,16u,20u,0,0,0) == 1);
    assert(udeks_window_destroy(1) == 0);
    assert(udeks_window_create(1,1,15,0u,0u,320u,200u,0,0,0) == 1);
    assert(udeks_window_destroy(1) == 0);
    puts("16-bit-safe create bounds OK"); return 0;
}
'''


def generic_harness():
    tree = ast.parse((ROOT / 'tests/test_window_manager_budget.py').read_text())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and
                  n.name == 'test_real_c_manager_matches_baseline_geometry_state_and_all_drawing_calls')
    harness = next(ast.literal_eval(n.value) for n in method.body if isinstance(n, ast.Assign)
                   and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'harness')
    return harness.split('int main(void) {', 1)[0]


class WindowCreateBoundsTests(unittest.TestCase):
    def test_target_width_guard_is_installed_in_both_managers(self):
        for name in ('window_manager.c', 'window_manager_cached.c'):
            source = (ROOT / 'src/services/window' / name).read_text()
            self.assertEqual(source.count(GUARD), 1, name)
            self.assertNotIn('x + width > UDEKS_VIC_WIDTH', source)

    def test_real_create_paths_reject_wrap_and_accept_edges(self):
        from test_window_cache_partial_manager import transport
        cached_harness = transport((ROOT / 'bench/window-cache-manager/occlusion-host.inc').read_text())
        cached_harness = cached_harness.split('int main(void){', 1)[0]
        cases = '#include <stdint.h>\n#include <assert.h>\n#include <string.h>\n' + CASES
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            generic = (ROOT / 'src/services/window/window_manager.c').read_text().replace(
                '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))',
                'test_status[offset]')
            cached = (ROOT / 'src/services/window/window_manager_cached.c').read_text().replace(
                '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))',
                'test_status[offset]')
            outputs = (
                compile_run(work, 'generic', generic_harness().replace('SOURCE', generic) + cases),
                compile_run(work, 'cached', '#define UDEKS_CACHE_MANAGER_HOST_TEST\n' +
                    cached_harness.replace('SOURCE', cached) + cases,
                    (ROOT / 'src/services/window/move_cache_state.c',)),
            )
        for output in outputs:
            self.assertTrue(output.endswith(b'16-bit-safe create bounds OK\n'))


if __name__ == '__main__':
    unittest.main()
