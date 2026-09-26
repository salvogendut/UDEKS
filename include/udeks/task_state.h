/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TASK_STATE_H
#define UDEKS_TASK_STATE_H

/*
 * Compiler-neutral task lifecycle 0.1. See abi/tasks.md for the transition
 * rules and the published diagnostic record.
 */

#define UDEKS_TASK_STATE_STATUS_BASE     0xF110u
#define UDEKS_TASK_STATE_STATUS_SIZE     16u

#define UDEKS_TASK_STATE_ABI_MAJOR       0u
#define UDEKS_TASK_STATE_ABI_MINOR       1u

#define UDEKS_TASK_MAX_TASKS             8u
#define UDEKS_TASK_ID_NONE               0u

#define UDEKS_TASK_STATE_FREE            0u
#define UDEKS_TASK_STATE_NEW             1u
#define UDEKS_TASK_STATE_RUNNABLE        2u
#define UDEKS_TASK_STATE_RUNNING         3u
#define UDEKS_TASK_STATE_WAITING         4u
#define UDEKS_TASK_STATE_STOPPED         5u
#define UDEKS_TASK_STATE_ZOMBIE          6u

#define UDEKS_TASK_EVENT_CREATE          1u
#define UDEKS_TASK_EVENT_ADMIT           2u
#define UDEKS_TASK_EVENT_DISPATCH        3u
#define UDEKS_TASK_EVENT_YIELD           4u
#define UDEKS_TASK_EVENT_BLOCK           5u
#define UDEKS_TASK_EVENT_UNBLOCK         6u
#define UDEKS_TASK_EVENT_STOP            7u
#define UDEKS_TASK_EVENT_CONTINUE        8u
#define UDEKS_TASK_EVENT_EXIT            9u
#define UDEKS_TASK_EVENT_REAP            10u
#define UDEKS_TASK_EVENT_CANCEL          11u

#define UDEKS_TASK_WAIT_NONE             0u
#define UDEKS_TASK_WAIT_CHILD            1u
#define UDEKS_TASK_WAIT_INPUT            2u
#define UDEKS_TASK_WAIT_TIMER            3u
#define UDEKS_TASK_WAIT_Z80              4u
#define UDEKS_TASK_WAIT_TERMINAL         5u

#define UDEKS_TASK_FLAG_USER             0x01u
#define UDEKS_TASK_FLAG_PERSISTENT       0x02u

#define UDEKS_TASK_OK                    0u
#define UDEKS_TASK_BAD_ID                1u
#define UDEKS_TASK_BAD_STATE             2u
#define UDEKS_TASK_EXISTS                3u
#define UDEKS_TASK_TABLE_FULL            4u
#define UDEKS_TASK_BAD_REASON            5u
#define UDEKS_TASK_BUSY                  6u
#define UDEKS_TASK_BAD_EVENT             7u

#define UDEKS_TASK_STATE_UNINITIALIZED   0u
#define UDEKS_TASK_STATE_READY           1u
#define UDEKS_TASK_STATE_ERROR           0x80u

/* Record offsets published at UDEKS_TASK_STATE_STATUS_BASE. */
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

/* Clears the table and counters. Returns UDEKS_TASK_OK. */
unsigned char udeks_task_state_reset(void);

/* Allocates an explicit id in UDEKS_TASK_STATE_FREE as NEW. */
unsigned char udeks_task_state_create(
    unsigned char id, unsigned char parent, unsigned char flags);

/* Applies one lifecycle event. The argument is a wait reason for BLOCK and
 * an exit status for EXIT; every other event ignores it. */
unsigned char udeks_task_state_apply(
    unsigned char id, unsigned char event, unsigned char argument);

/* Reads derived scheduler state. Invalid ids report 0xFF for state. */
unsigned char udeks_task_state_get(unsigned char id);
unsigned char udeks_task_state_current(void);
unsigned char udeks_task_state_runnable_count(void);
unsigned char udeks_task_state_defined_count(void);
unsigned int udeks_task_state_switch_count(void);
unsigned char udeks_task_state_rejected_count(void);
unsigned char udeks_task_state_canary_failures(void);

/* Reserved for the qualified context path once it checks stack canaries. */
void udeks_task_state_note_canary_failure(void);

/* Writes the 16-byte UTSK diagnostic record to a caller-owned buffer. */
void udeks_task_state_publish(unsigned char *record);

#endif
