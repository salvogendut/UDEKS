/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TASK_H
#define UDEKS_TASK_H

#define UDEKS_TASK_STATUS_BASE          0xF280u
#define UDEKS_TASK_STATUS_SIZE          32u
#define UDEKS_TASK_STATE_OFFSET         5u
#define UDEKS_TASK_ERROR_OFFSET         6u
#define UDEKS_TASK_EXIT_OFFSET          7u
#define UDEKS_TASK_HEADER_BASE          0xF290u
#define UDEKS_TASK_LOADER_ENTRY         0xFA00u
#define UDEKS_TASK_STACK_TOP            0xF7F0u

#define UDEKS_TASK_STATE_IDLE           0u
#define UDEKS_TASK_STATE_VALIDATING     1u
#define UDEKS_TASK_STATE_RUNNING        2u
#define UDEKS_TASK_STATE_EXITED         3u
#define UDEKS_TASK_STATE_ERROR          0x80u

#define UDEKS_TASK_OK                    0u
#define UDEKS_TASK_BAD_SYSCALL_ABI       2u
#define UDEKS_TASK_BUSY                  3u
#define UDEKS_TASK_BAD_MAGIC             4u
#define UDEKS_TASK_BAD_VERSION           5u
#define UDEKS_TASK_BAD_CPU               6u
#define UDEKS_TASK_BAD_FLAGS             7u
#define UDEKS_TASK_BAD_LOAD              8u
#define UDEKS_TASK_BAD_SIZE              9u
#define UDEKS_TASK_BAD_ENTRY             10u
#define UDEKS_TASK_NOT_FOUND              11u
#define UDEKS_TASK_BAD_BOOTFS             12u

typedef unsigned char (*udeks_task_loader_entry)(
    unsigned char count, unsigned char **arguments);

#endif
