# SPDX-License-Identifier: GPL-3.0-or-later
"""Private row-provider ordering/progress proof; no resident integration."""
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
#include "PROVIDER_HEADER"
static unsigned char pixels[200][320], clip_active, deferred, rejected;
static unsigned validations, preflights, draws, resets, acknowledgements;
static unsigned char trace[512];
static unsigned trace_len;
static void mark(unsigned char c) { assert(trace_len < sizeof(trace)); trace[trace_len++] = c; }
unsigned char repaint_client_validate(const struct udeks_repaint_lane_ticket *t) {
    ++validations; mark('V'); return udeks_lane_validate(t);
}
unsigned char repaint_client_ack(const struct udeks_repaint_lane_ticket *t, unsigned char more) {
    ++acknowledgements; mark('A'); assert(!clip_active);
    return udeks_lane_ack(t, more);
}
unsigned char repaint_client_ready(unsigned char handle, unsigned char row) {
    ++preflights; mark('P'); assert(handle == 1 && row >= 24 && row < 107);
    return deferred ? REPAINT_PROVIDER_DEFER : rejected ? UDEKS_REPAINT_INVALID : 0;
}
void repaint_client_set_clip(unsigned int x, unsigned char y, unsigned int w, unsigned char h) {
    mark('C'); assert(!clip_active && x == 13 && y == 24 && w == 94 && h == 83);
    clip_active = 1;
}
void repaint_client_draw_row(unsigned char handle, unsigned char row) {
    unsigned x;
    mark('D'); assert(clip_active && handle == 1); ++draws;
    for (x = 13; x < 107; ++x) pixels[row][x] = 1;
}
void repaint_client_reset_clip(void) { mark('R'); assert(clip_active); clip_active = 0; ++resets; }
static void unchanged(const struct udeks_repaint_lane *old, unsigned old_draws,
                      unsigned old_ack) {
    assert(memcmp(old, &udeks_repaint_lane, sizeof(*old)) == 0);
    assert(draws == old_draws && acknowledgements == old_ack && !clip_active);
}
int main(void) {
    const struct udeks_repaint_window window = {{10, 110, 10, 110}, 1, 1, 1};
    struct udeks_repaint_window wrong;
    const struct udeks_repaint_rect damage = {0, 320, 0, 200};
    struct udeks_repaint_lane_work work, bad;
    struct udeks_repaint_lane before;
    unsigned before_draws, before_ack, rows = 0, i;
    unsigned char result;

    udeks_lane_init(); assert(udeks_lane_request(&damage) == 0);
    for (i = 0; i < 200; ++i) {
        assert(udeks_lane_peek(&window, 1, &work) == 0);
        if (work.ticket.phase == UDEKS_REPAINT_CLIENT) break;
        assert(udeks_lane_ack(&work.ticket, 0) == 0);
    }
    assert(i < 200 && work.clip.top == 24 && work.clip.bottom == 107);
    before = udeks_repaint_lane; before_draws = draws; before_ack = acknowledgements;
    bad = work; bad.clip.right = 111;
    assert(repaint_client_step(&bad, &window) == UDEKS_REPAINT_INVALID);
    unchanged(&before, before_draws, before_ack);
    bad = work; bad.ticket.phase = UDEKS_REPAINT_RESTORE;
    assert(repaint_client_step(&bad, &window) == UDEKS_REPAINT_INVALID);
    unchanged(&before, before_draws, before_ack);
    assert(repaint_client_step(0, &window) == UDEKS_REPAINT_INVALID);
    unchanged(&before, before_draws, before_ack);
    wrong = window; wrong.handle = 2;
    assert(repaint_client_step(&work, &wrong) == UDEKS_REPAINT_STALE);
    unchanged(&before, before_draws, before_ack);
    wrong = window; wrong.rank = 2;
    assert(repaint_client_step(&work, &wrong) == UDEKS_REPAINT_STALE);
    unchanged(&before, before_draws, before_ack);
    wrong = window; wrong.flags = 0;
    assert(repaint_client_step(&work, &wrong) == UDEKS_REPAINT_STALE);
    unchanged(&before, before_draws, before_ack);
    bad = work; bad.ticket.cursor = 83;
    assert(repaint_client_step(&bad, &window) == UDEKS_REPAINT_STALE);
    unchanged(&before, before_draws, before_ack);

    deferred = 1;
    trace_len = 0;
    assert(repaint_client_step(&work, &window) == REPAINT_PROVIDER_DEFER);
    assert(trace_len == 2 && trace[0] == 'V' && trace[1] == 'P');
    unchanged(&before, before_draws, before_ack);
    deferred = 0; rejected = 1;
    assert(repaint_client_step(&work, &window) == UDEKS_REPAINT_INVALID);
    unchanged(&before, before_draws, before_ack);
    rejected = 0;
    do {
        trace_len = 0;
        result = repaint_client_step(&work, &window);
        assert(result == 0 && trace_len == 6);
        assert(memcmp(trace, "VPCDRA", 6) == 0 && !clip_active);
        ++rows;
        if (rows < 83) {
            assert(udeks_lane_peek(&window, 1, &work) == 0);
            assert(work.ticket.phase == UDEKS_REPAINT_CLIENT);
        }
    } while (rows < 83);
    assert(draws == 83 && resets == 83 && acknowledgements == 83);
    for (i = 24; i < 107; ++i) {
        unsigned x; for (x = 13; x < 107; ++x) assert(pixels[i][x] == 1);
    }
    before = udeks_repaint_lane; before_draws = draws; before_ack = acknowledgements;
    trace_len = 0;
    assert(repaint_client_step(&work, &window) == UDEKS_REPAINT_STALE);
    assert(trace_len == 1 && trace[0] == 'V');
    unchanged(&before, before_draws, before_ack);

    /* A structural change withdraws the ticket before the old provider can
     * read any stale application state or touch the clip/pixels. */
    assert(udeks_lane_changed(&damage) == 0);
    before = udeks_repaint_lane;
    assert(repaint_client_step(&work, &window) == UDEKS_REPAINT_STALE);
    unchanged(&before, before_draws, before_ack);
    puts("client row contract/order/cancellation OK"); return 0;
}
'''


class RepaintProviderTests(unittest.TestCase):
    def test_private_client_row_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            output = compile_run(Path(directory), 'provider', HARNESS.replace(
                'PROVIDER_HEADER', str(ROOT / 'bench/window-repaint-provider/provider.h')), (
                ROOT / 'bench/window-repaint-provider/provider.c',
                ROOT / 'src/services/window/repaint_lane.c'))
        self.assertEqual(output, b'client row contract/order/cancellation OK\n')


if __name__ == '__main__':
    unittest.main()
