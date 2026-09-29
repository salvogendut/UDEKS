/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TASK_BANK_H
#define UDEKS_TASK_BANK_H

#define UDEKS_TASK_BANK_GATE_BASE         0xFF05u
#define UDEKS_TASK_BANK_RESET             0xFF10u
#define UDEKS_TASK_BANK_POLL              0xFF13u
#define UDEKS_TASK_BANK_REQUEST           0xFF16u
#define UDEKS_TASK_BANK_ENTRY             0x9000u
#define UDEKS_TASK_BANK_CONTEXT           0xE2E2u
#define UDEKS_TASK_BANK_STACK_TOP         0xEFF0u
#define UDEKS_TASK_BANK_CC65_ZP_SIZE       0x1Eu

#define UDEKS_TASK_BANK_STATE_EMPTY       0u
#define UDEKS_TASK_BANK_STATE_READY       1u
#define UDEKS_TASK_BANK_STATE_RUNNING     2u
#define UDEKS_TASK_BANK_STATE_ERROR       0x80u

#define UDEKS_TASK_BANK_OK                0u
#define UDEKS_TASK_BANK_NOT_READY         1u

typedef unsigned char (*udeks_task_bank_entry)(void);
typedef void (*udeks_task_bank_reset_entry)(void);
typedef unsigned char (*udeks_task_bank_poll_entry)(void);

#endif
