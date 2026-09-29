/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TASK_SCHEDULER_H
#define UDEKS_TASK_SCHEDULER_H

/*
 * Bounded cooperative run-queue policy for Tasking 0.1. The lifecycle table
 * remains authoritative; this module only selects among RUNNABLE entries and
 * never mutates task state.
 */

#define UDEKS_SCHEDULER_NO_TASK 0u

/* Returns the first RUNNABLE task after after_id, wrapping once through the
 * fixed lifecycle table. after_id must be a valid task id or zero; zero starts
 * at task 1. Returns UDEKS_SCHEDULER_NO_TASK when no runnable task exists. */
unsigned char udeks_scheduler_select_next(unsigned char after_id);

#endif
