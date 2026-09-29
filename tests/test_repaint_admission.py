# SPDX-License-Identifier: GPL-3.0-or-later
"""Synchronous private lease/retry contract; not a public window ABI."""
from pathlib import Path
import tempfile
import unittest

from test_window_cache_manager import compile_run

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "udeks/repaint_lane.h"
#include "ADMISSION_HEADER"
#include "EDIT_HEADER"
static unsigned char nmi_pending, scene_live;
static void nmi_stub_model(void) { nmi_pending = 1; } /* no manager access */
int main(void) {
    const struct udeks_repaint_rect box = {20, 80, 20, 80};
    struct udeks_repaint_lane before;
    unsigned char owner;
    udeks_lane_init(); before = udeks_repaint_lane;
    assert(repaint_admission_owner == REPAINT_ADMISSION_FREE);
    assert(repaint_admission_try(0) == REPAINT_ADMISSION_INVALID);
    assert(repaint_admission_try(5) == REPAINT_ADMISSION_INVALID);
    assert(repaint_admission_owner == REPAINT_ADMISSION_FREE);

    assert(repaint_admission_try(REPAINT_ADMISSION_RASTER) == 0);
    owner = repaint_admission_owner;
    nmi_stub_model();
    assert(repaint_admission_owner == owner && nmi_pending == 1);
    assert(repaint_admission_try(REPAINT_ADMISSION_RASTER) == REPAINT_ADMISSION_DEFERRED);
    assert(repaint_admission_try(REPAINT_ADMISSION_EDIT) == REPAINT_ADMISSION_DEFERRED);
    assert(repaint_edit_begin(0, &box) == REPAINT_ADMISSION_DEFERRED);
    assert(!scene_live && memcmp(&before, &udeks_repaint_lane, sizeof(before)) == 0);
    assert(repaint_admission_release(REPAINT_ADMISSION_EDIT) == REPAINT_ADMISSION_INVALID);
    assert(repaint_admission_owner == owner);
    assert(repaint_admission_release(REPAINT_ADMISSION_RASTER) == 0);
    assert(repaint_admission_owner == REPAINT_ADMISSION_FREE);

    assert(repaint_edit_begin(0, 0) == UDEKS_REPAINT_INVALID);
    assert(repaint_admission_owner == REPAINT_ADMISSION_FREE);
    assert(memcmp(&before, &udeks_repaint_lane, sizeof(before)) == 0);
    assert(repaint_edit_begin(0, &box) == UDEKS_REPAINT_OK);
    assert(repaint_admission_owner == REPAINT_ADMISSION_EDIT);
    scene_live = 1; /* Only after the ticket has been fenced. */
    assert(repaint_admission_try(REPAINT_ADMISSION_CLIENT) == REPAINT_ADMISSION_DEFERRED);
    assert(repaint_edit_end() == 0);
    assert(scene_live);
    assert(repaint_admission_try(REPAINT_ADMISSION_CLIENT) == 0);
    assert(repaint_admission_try(REPAINT_ADMISSION_CACHE) == REPAINT_ADMISSION_DEFERRED);
    assert(repaint_admission_release(REPAINT_ADMISSION_CLIENT) == 0);
    assert(repaint_admission_try(REPAINT_ADMISSION_CACHE) == 0);
    assert(repaint_admission_release(REPAINT_ADMISSION_CACHE) == 0);
    assert(repaint_admission_release(REPAINT_ADMISSION_CACHE) == REPAINT_ADMISSION_INVALID);
    assert(repaint_admission_owner == REPAINT_ADMISSION_FREE);
    udeks_lane_init(); udeks_repaint_lane.epoch = 0xFFFFu;
    assert(repaint_edit_begin(&box, 0) == UDEKS_REPAINT_EXHAUSTED);
    assert(repaint_admission_owner == REPAINT_ADMISSION_FREE);
    assert(scene_live && (udeks_repaint_lane.state & 7u) == UDEKS_REPAINT_FAILED);
    puts("synchronous admission/retry/release OK"); return 0;
}
'''


class RepaintAdmissionTests(unittest.TestCase):
    def test_installed_nmi_stub_remains_record_only(self):
        common = (ROOT / 'src/8502/nmi-common.inc').read_text()
        body = common.split('.macro UDEKS_NMI_STUB\n', 1)[1].split('.endmacro', 1)[0]
        self.assertEqual([line.strip() for line in body.splitlines() if line.strip()],
            ['pha', 'lda #$01', 'sta UDEKS_NMI_PENDING', 'pla', 'rti'])
        installed = (ROOT / 'src/8502/nmi.s').read_text()
        self.assertIn('nmi_stub:\n        UDEKS_NMI_STUB\nnmi_stub_end:', installed)

    def test_private_synchronous_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            output = compile_run(Path(directory), 'admission', HARNESS.replace(
                'ADMISSION_HEADER', str(ROOT / 'bench/window-repaint-admission/admission.h')).replace(
                'EDIT_HEADER', str(ROOT / 'bench/window-repaint-edit/fence.h')), (
                ROOT / 'bench/window-repaint-admission/admission.c',
                ROOT / 'bench/window-repaint-admission/transaction.c',
                ROOT / 'bench/window-repaint-edit/fence.c',
                ROOT / 'src/services/window/repaint_lane.c'))
        self.assertEqual(output, b'synchronous admission/retry/release OK\n')


if __name__ == '__main__':
    unittest.main()
