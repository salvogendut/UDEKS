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
 * be tested without the resident scheduler. The operation range is checked
 * first, so an unknown operation is ENOSYS regardless of any other field.
 * Returns zero or a UDEKS_TREQ_* errno:
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
 * Spawn candidate preflight. The loader resolves the executable and proposes
 * a placement; it calls this before any allocation metadata changes. A
 * candidate is a 20-byte record: the unchanged 16-byte UDEX header followed
 * by the proposed stack base and size. Multi-byte fields are little-endian,
 * and the reserved table holds 4-byte entries of base and size words for
 * every region the candidate must not overlap. Range arithmetic is inclusive,
 * so a valid range may end exactly at the top of the address space ($FFFF).
 *
 * The header fields are validated against UDEX 0.1: major 0, minor 0 or 1,
 * 8502 CPU, and flags 0, persistent ($01), or managed ($02); unknown bits and
 * the combined $03 value are rejected.
 *
 * Returns zero, or:
 *
 *   ENOEXEC  wrong magic, unsupported major or minor version, unsupported
 *            CPU, invalid executable flags, zero-length image, or an entry
 *            outside the image;
 *   EINVAL   missing, under-sized, overflowing, or image-overlapping stack;
 *   ENOMEM   address-space overflow or overlap with a reserved region.
 */
#define UDEKS_TASK_POLICY_CPU_8502       1u
#define UDEKS_TASK_POLICY_MAJOR_UDEX     0u
#define UDEKS_TASK_POLICY_MINOR_UDEX     1u
#define UDEKS_TASK_POLICY_FLAG_PERSISTENT 0x01u
#define UDEKS_TASK_POLICY_FLAG_MANAGED   0x02u
#define UDEKS_TASK_POLICY_STACK_MIN      32u
#define UDEKS_TASK_POLICY_CANDIDATE_SIZE 20u
#define UDEKS_TASK_POLICY_RESERVED_SIZE  4u

#define UDEKS_TASK_CANDIDATE_MAGIC       0u
#define UDEKS_TASK_CANDIDATE_MAJOR       4u
#define UDEKS_TASK_CANDIDATE_MINOR       5u
#define UDEKS_TASK_CANDIDATE_CPU         6u
#define UDEKS_TASK_CANDIDATE_FLAGS       7u
#define UDEKS_TASK_CANDIDATE_IMAGE_BASE  8u
#define UDEKS_TASK_CANDIDATE_IMAGE_SIZE  10u
#define UDEKS_TASK_CANDIDATE_BSS_SIZE    12u
#define UDEKS_TASK_CANDIDATE_ENTRY       14u
#define UDEKS_TASK_CANDIDATE_STACK_BASE  16u
#define UDEKS_TASK_CANDIDATE_STACK_SIZE  18u

unsigned char udeks_task_policy_validate_spawn_candidate(
    const unsigned char *candidate,
    const unsigned char *reserved, unsigned char reserved_count);

#endif
