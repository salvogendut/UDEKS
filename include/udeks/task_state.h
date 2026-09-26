/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TASK_STATE_H
#define UDEKS_TASK_STATE_H

/*
 * Compiler-neutral task lifecycle 0.1. See abi/tasks.md for the transition
 * rules and the published diagnostic record. The UDEKS_LIFECYCLE_* macros and
 * udeks_lifecycle_* calls are deliberately distinct from the loader record in
 * task.h so a source may include both headers.
 */

#define UDEKS_LIFECYCLE_STATUS_BASE      0xF110u
#define UDEKS_LIFECYCLE_STATUS_SIZE      16u

#define UDEKS_LIFECYCLE_ABI_MAJOR        0u
#define UDEKS_LIFECYCLE_ABI_MINOR        1u

#define UDEKS_LIFECYCLE_MAX_TASKS        8u
#define UDEKS_LIFECYCLE_ID_NONE          0u
#define UDEKS_LIFECYCLE_INVALID          0xFFu

#define UDEKS_LIFECYCLE_STATE_FREE       0u
#define UDEKS_LIFECYCLE_STATE_NEW        1u
#define UDEKS_LIFECYCLE_STATE_RUNNABLE   2u
#define UDEKS_LIFECYCLE_STATE_RUNNING    3u
#define UDEKS_LIFECYCLE_STATE_WAITING    4u
#define UDEKS_LIFECYCLE_STATE_STOPPED    5u
#define UDEKS_LIFECYCLE_STATE_ZOMBIE     6u

#define UDEKS_LIFECYCLE_EVENT_CREATE     1u
#define UDEKS_LIFECYCLE_EVENT_ADMIT      2u
#define UDEKS_LIFECYCLE_EVENT_DISPATCH   3u
#define UDEKS_LIFECYCLE_EVENT_YIELD      4u
#define UDEKS_LIFECYCLE_EVENT_BLOCK      5u
#define UDEKS_LIFECYCLE_EVENT_UNBLOCK    6u
#define UDEKS_LIFECYCLE_EVENT_STOP       7u
#define UDEKS_LIFECYCLE_EVENT_CONTINUE   8u
#define UDEKS_LIFECYCLE_EVENT_EXIT       9u
#define UDEKS_LIFECYCLE_EVENT_REAP       10u
#define UDEKS_LIFECYCLE_EVENT_CANCEL     11u

#define UDEKS_LIFECYCLE_WAIT_NONE        0u
#define UDEKS_LIFECYCLE_WAIT_CHILD       1u
#define UDEKS_LIFECYCLE_WAIT_INPUT       2u
#define UDEKS_LIFECYCLE_WAIT_TIMER       3u
#define UDEKS_LIFECYCLE_WAIT_Z80         4u
#define UDEKS_LIFECYCLE_WAIT_TERMINAL    5u

#define UDEKS_LIFECYCLE_FLAG_USER        0x01u
#define UDEKS_LIFECYCLE_FLAG_PERSISTENT  0x02u

#define UDEKS_LIFECYCLE_OK               0u
#define UDEKS_LIFECYCLE_BAD_ID           1u
#define UDEKS_LIFECYCLE_BAD_STATE        2u
#define UDEKS_LIFECYCLE_EXISTS           3u
#define UDEKS_LIFECYCLE_TABLE_FULL       4u
#define UDEKS_LIFECYCLE_BAD_REASON       5u
#define UDEKS_LIFECYCLE_BUSY             6u
#define UDEKS_LIFECYCLE_BAD_EVENT        7u
#define UDEKS_LIFECYCLE_BAD_FLAGS        8u

#define UDEKS_LIFECYCLE_UNINITIALIZED    0u
#define UDEKS_LIFECYCLE_READY            1u
#define UDEKS_LIFECYCLE_ERROR            0x80u

/* Record offsets published at UDEKS_LIFECYCLE_STATUS_BASE. */
#define UDEKS_UTSK_MAGIC0                0u
#define UDEKS_UTSK_MAGIC1                1u
#define UDEKS_UTSK_MAGIC2                2u
#define UDEKS_UTSK_MAGIC3                3u
#define UDEKS_UTSK_ABI_MAJOR             4u
#define UDEKS_UTSK_ABI_MINOR             5u
#define UDEKS_UTSK_STATE                 6u
#define UDEKS_UTSK_CURRENT               7u
#define UDEKS_UTSK_RUNNABLE              8u
#define UDEKS_UTSK_DEFINED               9u
#define UDEKS_UTSK_REJECTED              10u
#define UDEKS_UTSK_CANARY                11u
#define UDEKS_UTSK_SWITCHES_LO           12u
#define UDEKS_UTSK_SWITCHES_HI           13u
#define UDEKS_UTSK_LAST_EVENT            14u
#define UDEKS_UTSK_RESERVED              15u

/* Clears the table and counters. Returns UDEKS_LIFECYCLE_OK. */
unsigned char udeks_lifecycle_reset(void);

/* Allocates an explicit id in UDEKS_LIFECYCLE_STATE_FREE as NEW. A nonzero
 * parent must name a different, live task; see abi/tasks.md. */
unsigned char udeks_lifecycle_create(
    unsigned char id, unsigned char parent, unsigned char flags);

/* Applies one lifecycle event. The argument is a wait reason for BLOCK and
 * an exit or termination status for EXIT and CANCEL; other events ignore it. */
unsigned char udeks_lifecycle_apply(
    unsigned char id, unsigned char event, unsigned char argument);

/* Reads derived scheduler state. Invalid ids report UDEKS_LIFECYCLE_INVALID. */
unsigned char udeks_lifecycle_get(unsigned char id);
unsigned char udeks_lifecycle_parent(unsigned char id);
unsigned char udeks_lifecycle_wait_reason(unsigned char id);
unsigned char udeks_lifecycle_exit_status(unsigned char id);
unsigned char udeks_lifecycle_current(void);
unsigned char udeks_lifecycle_runnable_count(void);
unsigned char udeks_lifecycle_defined_count(void);
unsigned int udeks_lifecycle_switch_count(void);
unsigned char udeks_lifecycle_rejected_count(void);
unsigned char udeks_lifecycle_canary_failures(void);

/* Reserved for the qualified context path once it checks stack canaries. */
void udeks_lifecycle_note_canary_failure(void);

/* Writes the 16-byte UTSK diagnostic record to a caller-owned buffer. */
void udeks_lifecycle_publish(unsigned char *record);

#endif
