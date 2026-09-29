# SPDX-License-Identifier: GPL-3.0-or-later
"""Pre-edit retry and old/new damage union with the real private lane."""
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
#include "EDIT_HEADER"

static void same(const struct udeks_repaint_lane *before) {
    assert(memcmp(before, &udeks_repaint_lane, sizeof(*before)) == 0);
}
static void rect(const struct udeks_repaint_rect *r,
                 unsigned l, unsigned rr, unsigned t, unsigned b) {
    assert(r->left == l && r->right == rr && r->top == t && r->bottom == b);
}
int main(void) {
    const struct udeks_repaint_rect first = {40, 100, 30, 90};
    const struct udeks_repaint_rect moved = {80, 140, 60, 120};
    const struct udeks_repaint_rect extra = {10, 20, 10, 20};
    const struct udeks_repaint_rect bad = {300, 321, 0, 20};
    const struct udeks_repaint_window view = {{40, 100, 30, 90}, 1, 1, 1};
    struct udeks_repaint_lane_work work;
    struct udeks_repaint_lane before;
    struct udeks_repaint_rect scene = first;
    unsigned char live = 0, close_count = 0;
    unsigned i, mode, availability;
    unsigned char reference_result, trusted_result;
    struct udeks_repaint_lane reference;
    struct udeks_repaint_rect a, b;

    udeks_lane_init(); before = udeks_repaint_lane;
    assert(repaint_edit_fence(0, 0, &first) == REPAINT_EDIT_DEFERRED);
    same(&before); assert(!live);
    assert(repaint_edit_fence(1, 0, 0) == UDEKS_REPAINT_INVALID);
    same(&before);
    assert(repaint_edit_fence(1, &bad, &first) == UDEKS_REPAINT_INVALID);
    same(&before);
    assert(repaint_edit_fence(1, 0, &first) == UDEKS_REPAINT_OK);
    live = 1; /* Publication is legal only after fence acceptance. */
    assert(live && (udeks_repaint_lane.state & UDEKS_LANE_PENDING));
    rect(&udeks_repaint_lane.pending, 40, 100, 30, 90);
    assert(udeks_lane_peek(&view, 1, &work) == UDEKS_REPAINT_OK);
    assert(udeks_lane_validate(&work.ticket) == UDEKS_REPAINT_OK);

    before = udeks_repaint_lane;
    assert(repaint_edit_fence(0, &scene, &moved) == REPAINT_EDIT_DEFERRED);
    same(&before); rect(&scene, 40, 100, 30, 90);
    assert(udeks_lane_validate(&work.ticket) == UDEKS_REPAINT_OK);
    assert(repaint_edit_fence(1, &scene, &moved) == UDEKS_REPAINT_OK);
    scene = moved; /* Old work is withdrawn before editing the scene. */
    assert(udeks_lane_validate(&work.ticket) == UDEKS_REPAINT_STALE);
    rect(&udeks_repaint_lane.pending, 40, 140, 30, 120);
    assert(udeks_lane_request(&extra) == UDEKS_REPAINT_OK);
    rect(&udeks_repaint_lane.pending, 10, 140, 10, 120);

    before = udeks_repaint_lane;
    assert(repaint_edit_fence(0, &scene, 0) == REPAINT_EDIT_DEFERRED);
    same(&before); assert(live && close_count == 0);
    assert(repaint_edit_fence(1, &scene, 0) == UDEKS_REPAINT_OK);
    live = 0; ++close_count;
    assert(!live && close_count == 1);
    rect(&udeks_repaint_lane.pending, 10, 140, 10, 120);

    /* Exhaustion is fail-closed: the lane enters FAILED, but a caller must
     * not publish or retire a window on a non-OK result. */
    udeks_lane_init(); udeks_repaint_lane.epoch = 0xFFFFu;
    scene = first; live = 1;
    assert(repaint_edit_fence(1, &scene, &moved) == UDEKS_REPAINT_EXHAUSTED);
    assert(live && close_count == 1);
    rect(&scene, 40, 100, 30, 90);
    assert((udeks_repaint_lane.state & 7u) == UDEKS_REPAINT_FAILED);

    /* The smaller trusted variant is equivalent only over validated manager
     * rectangles; all external/unchecked geometry stays with the reference. */
    for (i = 0; i < 300; ++i) {
        a.left = (i * 29u) % 300u; a.right = a.left + 1u + i % 20u;
        a.top = (i * 17u) % 180u; a.bottom = a.top + 1u + i % 20u;
        b.left = (i * 31u) % 300u; b.right = b.left + 1u + i % 20u;
        b.top = (i * 19u) % 180u; b.bottom = b.top + 1u + i % 20u;
        for (mode = 0; mode < 3; ++mode) {
            const struct udeks_repaint_rect *old = mode == 0 ? 0 : &a;
            const struct udeks_repaint_rect *newer = mode == 1 ? 0 : &b;
            for (availability = 0; availability < 2; ++availability) {
                udeks_lane_init(); assert(udeks_lane_request(&first) == 0);
                assert(udeks_lane_peek(&view, 1, &work) == 0);
                before = udeks_repaint_lane;
                reference_result = repaint_edit_fence(availability, old, newer);
                reference = udeks_repaint_lane;
                udeks_repaint_lane = before;
                trusted_result = repaint_edit_fence_trusted(availability, old, newer);
                assert(reference_result == trusted_result);
                assert(memcmp(&reference, &udeks_repaint_lane, sizeof(reference)) == 0);
            }
        }
    }
    puts("pre-edit defer/withdraw/union/exhaustion OK"); return 0;
}
'''


class RepaintEditTests(unittest.TestCase):
    def test_private_pre_edit_fence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = compile_run(Path(directory), 'edit', HARNESS.replace(
                'EDIT_HEADER', str(ROOT / 'bench/window-repaint-edit/fence.h')), (
                ROOT / 'bench/window-repaint-edit/fence.c',
                ROOT / 'bench/window-repaint-edit/fence_trusted.c',
                ROOT / 'src/services/window/repaint_lane.c'))
        self.assertEqual(output, b'pre-edit defer/withdraw/union/exhaustion OK\n')


if __name__ == '__main__':
    unittest.main()
