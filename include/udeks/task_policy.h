/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TASK_POLICY_H
#define UDEKS_TASK_POLICY_H

/*
 * Host-testable validation for ABI 0.3 lifecycle requests. See
 * abi/task-request.md for the frozen request and response layouts.
 *
 * These functions never mutate the task table: a rejected request leaves
 * lifecycle state, allocation metadata, and counters untouched, as required
 * by the rejection-atomicity rule.
 */

/* Validates one lifecycle request against the current table. The caller id
 * must name a defined task. Returns zero or a UDEKS_TREQ_* errno:
 *
 *   ENOSYS  operation is not an ABI 0.3 lifecycle operation;
 *   EINVAL  count, flags, name, or range is malformed;
 *   ESRCH   caller or CANCEL target is not a defined task;
 *   ECHILD  WAITPID target is not a child of the caller.
 *
 * On success the decoded values are written through the out parameters:
 *
 *   task_id  resolved target or matched child id, or id 0 when unused;
 *   status   exit or termination status, or 0 when unused;
 *   ticks    SLEEP ticks in 1/60 s units, or 0 when unused.
 *
 * A successful WAITPID leaves the child state to the caller: inspect
 * udeks_lifecycle_get(task_id) to distinguish a reapable zombie (result 1)
 * from a live child (NOHANG completes with result 0; a blocking wait
 * suspends).
 */
unsigned char udeks_task_policy_validate(
    unsigned char operation, unsigned char flags, unsigned char count,
    const unsigned char *payload, unsigned char caller_id,
    unsigned char *task_id, unsigned char *status, unsigned int *ticks);

#endif
