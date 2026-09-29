# SPDX-License-Identifier: GPL-3.0-or-later
"""Private full-window restore: exactly one cache row per admitted poll."""
from pathlib import Path
import tempfile
import unittest

from test_window_cache_manager import compile_run

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include "udeks/window_cache_state.h"
#include "RESTORE_HEADER"
#include "ADMISSION_HEADER"
static unsigned char phase=UDEKS_CACHE_READY, owner=1, row;
static unsigned char image_status, begin_failed, step_failed, ack_failed, repair_failed;
static unsigned calls_begin, calls_step, calls_ack, calls_commit, calls_repair;
static unsigned int expected_cursor;
static unsigned char height=18;
unsigned char repaint_restore_validate(const struct udeks_repaint_lane_ticket *t) {
    return t->epoch==1 && t->cursor==expected_cursor ? UDEKS_REPAINT_OK : UDEKS_REPAINT_STALE;
}
unsigned char repaint_restore_ack(const struct udeks_repaint_lane_ticket *t,unsigned char more) {
    ++calls_ack;
    if (ack_failed || t->cursor!=expected_cursor ||
        more!=(expected_cursor+1u<height)) return UDEKS_REPAINT_STALE;
    ++expected_cursor;return UDEKS_REPAINT_OK;
}
unsigned char repaint_restore_image_valid(unsigned char h) {
    return h==owner ? image_status : UDEKS_CACHE_INVALID;
}
unsigned char repaint_restore_phase(void) {return phase;}
unsigned char repaint_restore_owner(void) {return owner;}
unsigned char repaint_restore_row(void) {return row;}
unsigned char repaint_restore_begin_full(unsigned char h) {
    ++calls_begin;
    if (begin_failed || h!=owner || phase!=UDEKS_CACHE_READY) return UDEKS_CACHE_INVALID;
    phase=UDEKS_CACHE_PASTING;row=0;return UDEKS_CACHE_OK;
}
unsigned char repaint_restore_step_row(void) {
    ++calls_step;
    if (step_failed) return UDEKS_CACHE_INVALID;
    assert(phase==UDEKS_CACHE_PASTING && row<height);
    if (++row==height) phase=UDEKS_CACHE_READY;
    return UDEKS_CACHE_OK;
}
void repaint_restore_commit(void) {++calls_commit;}
unsigned char repaint_restore_repair(unsigned char h,const struct udeks_repaint_rect *r) {
    ++calls_repair;assert(h==owner && r->left==20 && r->right==84);
    phase=UDEKS_CACHE_EMPTY;
    return repair_failed ? UDEKS_REPAINT_EXHAUSTED : UDEKS_REPAINT_OK;
}
static void reset(void) {
    phase=UDEKS_CACHE_READY;owner=1;row=0;expected_cursor=0;
    image_status=begin_failed=step_failed=ack_failed=repair_failed=0;
    calls_begin=calls_step=calls_ack=calls_commit=calls_repair=0;
    repaint_admission_owner=REPAINT_ADMISSION_FREE;
}
int main(void) {
    struct udeks_repaint_window window={{20,84,30,48},1,1,
        UDEKS_REPAINT_VISIBLE|UDEKS_REPAINT_RETAINED};
    struct udeks_repaint_lane_work work;
    unsigned i;
    work.clip=window.bounds;work.ticket.epoch=1;work.ticket.phase=UDEKS_REPAINT_RESTORE;
    work.ticket.selector=9;work.ticket.cursor=0;
    reset();
    assert(repaint_restore_step(0,&window)==UDEKS_REPAINT_INVALID);
    work.clip.left=21;
    assert(repaint_restore_step(&work,&window)==UDEKS_REPAINT_INVALID && calls_begin==0);
    work.clip=window.bounds;
    assert(repaint_admission_try(REPAINT_ADMISSION_EDIT)==0);
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_DEFERRED);
    assert(calls_begin==0 && calls_step==0 && repaint_admission_owner==REPAINT_ADMISSION_EDIT);
    assert(repaint_admission_release(REPAINT_ADMISSION_EDIT)==0);
    image_status=UDEKS_CACHE_BUSY;
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_DEFERRED);
    assert(calls_begin==0 && repaint_admission_owner==REPAINT_ADMISSION_FREE);
    image_status=0;begin_failed=1;
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_DEFERRED);
    assert(calls_begin==1 && calls_step==0 && phase==UDEKS_CACHE_READY);
    begin_failed=0;calls_begin=0;
    for(i=0;i<height;++i) {
        work.ticket.cursor=i;
        assert(repaint_restore_step(&work,&window)==UDEKS_REPAINT_OK);
        assert(calls_step==i+1 && expected_cursor==i+1 && row==i+1);
        assert(repaint_admission_owner==REPAINT_ADMISSION_FREE);
    }
    assert(calls_begin==1 && calls_ack==height && calls_commit==3 && calls_repair==0);
    assert(phase==UDEKS_CACHE_READY);
    work.ticket.cursor=0;
    assert(repaint_restore_step(&work,&window)==UDEKS_REPAINT_STALE);
    assert(calls_step==height);
    reset();
    assert(repaint_restore_step(&work,&window)==UDEKS_REPAINT_OK);
    work.ticket.cursor=1;row=0;
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_REPAIR_QUEUED);
    assert(calls_repair==1 && calls_step==1 && phase==UDEKS_CACHE_EMPTY);
    assert(repaint_admission_owner==REPAINT_ADMISSION_FREE);
    reset();work.ticket.cursor=0;image_status=UDEKS_CACHE_INVALID;
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_REPAIR_QUEUED);
    assert(calls_begin==0 && calls_step==0 && calls_repair==1);
    reset();
    assert(repaint_restore_step(&work,&window)==UDEKS_REPAINT_OK);
    work.ticket.cursor=1;image_status=UDEKS_CACHE_INVALID;
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_REPAIR_QUEUED);
    assert(calls_step==1 && calls_repair==1);
    reset();work.ticket.cursor=0;step_failed=1;
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_REPAIR_QUEUED);
    assert(calls_repair==1 && calls_ack==0 && repaint_admission_owner==0);
    reset();ack_failed=1;
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_REPAIR_QUEUED);
    assert(calls_step==1 && calls_ack==1 && calls_repair==1);
    reset();step_failed=repair_failed=1;
    assert(repaint_restore_step(&work,&window)==REPAINT_RESTORE_UNRECOVERABLE);
    assert(calls_repair==1 && repaint_admission_owner==0);
    puts("bounded full-window cache restore OK");return 0;
}
'''

LANE_HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include "udeks/window_cache_state.h"
#include "udeks/repaint_lane.h"
#include "RESTORE_HEADER"
static unsigned char phase=UDEKS_CACHE_READY, row, steps;
unsigned char repaint_restore_validate(const struct udeks_repaint_lane_ticket *t) {
    return udeks_lane_validate(t);
}
unsigned char repaint_restore_ack(const struct udeks_repaint_lane_ticket *t,unsigned char more) {
    return udeks_lane_ack(t,more);
}
unsigned char repaint_restore_image_valid(unsigned char h) {return h==1 ? 0 : 1;}
unsigned char repaint_restore_phase(void) {return phase;}
unsigned char repaint_restore_owner(void) {return 1;}
unsigned char repaint_restore_row(void) {return row;}
unsigned char repaint_restore_begin_full(unsigned char h) {
    assert(h==1 && phase==UDEKS_CACHE_READY && row==0);
    phase=UDEKS_CACHE_PASTING;return UDEKS_CACHE_OK;
}
unsigned char repaint_restore_step_row(void) {
    assert(phase==UDEKS_CACHE_PASTING && row<18);
    ++steps;++row;if(row==18) phase=UDEKS_CACHE_READY;
    return UDEKS_CACHE_OK;
}
void repaint_restore_commit(void) {}
unsigned char repaint_restore_repair(unsigned char h,const struct udeks_repaint_rect *r) {
    assert(h==1);return udeks_lane_changed(r);
}
static void reach_restore(const struct udeks_repaint_window *window,
                          struct udeks_repaint_lane_work *work) {
    unsigned i;
    for(i=0;i<100;++i) {
        assert(udeks_lane_peek(window,1,work)==UDEKS_REPAINT_OK);
        if(work->ticket.phase==UDEKS_REPAINT_RESTORE) return;
        assert(work->ticket.phase==UDEKS_REPAINT_CLEAR);
        assert(udeks_lane_ack(&work->ticket,UDEKS_REPAINT_DONE)==UDEKS_REPAINT_OK);
    }
    assert(0);
}
int main(void) {
    struct udeks_repaint_window window={{20,84,30,48},1,1,
        UDEKS_REPAINT_VISIBLE|UDEKS_REPAINT_RETAINED};
    struct udeks_repaint_rect partial={21,83,30,48};
    struct udeks_repaint_lane_work work;
    unsigned i;
    udeks_lane_init();
    assert(udeks_lane_request(&window.bounds)==UDEKS_REPAINT_OK);
    reach_restore(&window,&work);
    for(i=0;i<18;++i) {
        assert(work.ticket.cursor==i);
        assert(repaint_restore_step(&work,&window)==UDEKS_REPAINT_OK);
        assert(steps==i+1);
        assert(udeks_lane_peek(&window,1,&work)==UDEKS_REPAINT_OK);
    }
    assert(work.ticket.phase==UDEKS_REPAINT_COMMIT);
    assert(udeks_lane_abort()==UDEKS_REPAINT_OK);
    udeks_lane_init();phase=UDEKS_CACHE_READY;row=steps=0;
    assert(udeks_lane_request(&partial)==UDEKS_REPAINT_OK);
    reach_restore(&window,&work);
    assert(work.clip.left==21 && work.clip.right==83);
    assert(repaint_restore_step(&work,&window)==UDEKS_REPAINT_INVALID);
    assert(steps==0 && phase==UDEKS_CACHE_READY);
    puts("lane-backed full restore and clipped rejection OK");return 0;
}
'''


class RepaintCacheRestoreTests(unittest.TestCase):
    def test_one_row_per_poll_and_fail_closed_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            output = compile_run(Path(directory), 'cache_restore', HARNESS.replace(
                'RESTORE_HEADER', str(ROOT / 'bench/window-repaint-provider/cache_restore.h')).replace(
                'ADMISSION_HEADER', str(ROOT / 'bench/window-repaint-admission/admission.h')), (
                ROOT / 'bench/window-repaint-provider/cache_restore.c',
                ROOT / 'bench/window-repaint-admission/admission.c'))
        self.assertEqual(output, b'bounded full-window cache restore OK\n')

    def test_actual_lane_receipts_and_clipped_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            output = compile_run(Path(directory), 'cache_restore_lane',
                LANE_HARNESS.replace('RESTORE_HEADER', str(
                    ROOT / 'bench/window-repaint-provider/cache_restore.h')), (
                    ROOT / 'bench/window-repaint-provider/cache_restore.c',
                    ROOT / 'bench/window-repaint-admission/admission.c',
                    ROOT / 'src/services/window/repaint_lane.c'))
        self.assertEqual(output, b'lane-backed full restore and clipped rejection OK\n')


if __name__ == '__main__':
    unittest.main()
