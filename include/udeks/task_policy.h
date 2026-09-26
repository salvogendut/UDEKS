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

/* Validates one lifecycle request against the current table. The caller must
 * be the current RUNNING task; its id is passed explicitly so the policy can
 * be tested without the resident scheduler. Returns zero or a UDEKS_TREQ_*
 * errno:
 *
 *   ENOSYS  operation is not an ABI 0.3 lifecycle operation;
 *   ESRCH   caller is undefined, or a CANCEL target is not a live child;
 *   EINVAL  caller is not the current RUNNING task, descriptor is nonzero,
 *           or count, flags, name, or range is malformed;
 *   ECHILD  WAITPID target is not a child of the caller.
 *
 * On success the decoded values are written through the out parameters:
 *
 *   task_id  resolved target or matched zombie id; id 0 means "any child"
 *            for WAITPID and "unused" for the other operations;
 *   status   exit or termination status, or 0 when unused;
 *   ticks    SLEEP ticks in 1/60 s units, or 0 when unused.
 *
 * A successful WAITPID leaves reaping to the caller: inspect
 * udeks_lifecycle_get(task_id) when task_id is nonzero to distinguish a
 * reapable zombie (result 1) from a live child (NOHANG completes with result
 * 0; a blocking wait suspends). task_id 0 means the caller waits for any
 * child and the response is published when any child exits.
 */
unsigned char udeks_task_policy_validate(
    unsigned char operation, unsigned char flags, unsigned char count,
    unsigned char descriptor, const unsigned char *payload,
    unsigned char caller_id, unsigned char *task_id,
    unsigned char *status, unsigned int *ticks);

/*
 * Spawn candidate preflight. The loader parses the UDEX header, resolves the
 * executable, and proposes a placement; it calls this before any allocation
 * metadata changes. The candidate is a 13-byte record of 16-bit little-endian
 * words; the reserved table holds 4-byte entries of base and size words for
 * every region the candidate must not overlap.
 *
 * Returns zero, or:
 *
 *   ENOEXEC  unsupported CPU, zero-length image, or an entry outside the
 *            image;
 *   EINVAL   missing, under-sized, overflowing, or image-overlapping stack;
 *   ENOMEM   address-space overflow or overlap with a reserved region.
 */
#define UDEKS_TASK_POLICY_CPU_8502       1u
#define UDEKS_TASK_POLICY_STACK_MIN      32u
#define UDEKS_TASK_POLICY_CANDIDATE_SIZE 13u
#define UDEKS_TASK_POLICY_RESERVED_SIZE  4u

#define UDEKS_TASK_CANDIDATE_CPU         0u
#define UDEKS_TASK_CANDIDATE_IMAGE_BASE  1u
#define UDEKS_TASK_CANDIDATE_IMAGE_SIZE  3u
#define UDEKS_TASK_CANDIDATE_BSS_SIZE    5u
#define UDEKS_TASK_CANDIDATE_ENTRY       7u
#define UDEKS_TASK_CANDIDATE_STACK_BASE  9u
#define UDEKS_TASK_CANDIDATE_STACK_SIZE  11u

unsigned char udeks_task_policy_validate_spawn_candidate(
    const unsigned char *candidate,
    const unsigned char *reserved, unsigned char reserved_count);

#endif
