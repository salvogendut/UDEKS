/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_SYSCALL_H
#define UDEKS_SYSCALL_H

#define UDEKS_SYSCALL_TABLE_BASE        0xCF00u
#define UDEKS_SYSCALL_ABI_MAJOR         0u
#define UDEKS_SYSCALL_ABI_MINOR         3u
#define UDEKS_SYSCALL_HEADER_SIZE       16u
#define UDEKS_SYSCALL_VECTOR_SIZE       16u
#define UDEKS_SYSCALL_VECTOR_COUNT      4u

#define UDEKS_SYSCALL_MAGIC0            0u
#define UDEKS_SYSCALL_MAGIC1            1u
#define UDEKS_SYSCALL_MAGIC2            2u
#define UDEKS_SYSCALL_MAGIC3            3u
#define UDEKS_SYSCALL_MAJOR             4u
#define UDEKS_SYSCALL_MINOR             5u
#define UDEKS_SYSCALL_COUNT             6u
#define UDEKS_SYSCALL_HEADER_BYTES      7u

#define UDEKS_SYSCALL_WRITE_BYTE        0xCF10u
#define UDEKS_SYSCALL_WRITE             0xCF20u
#define UDEKS_SYSCALL_TASK_REQUEST      0xCF30u
#define UDEKS_SYSCALL_CLOCK_SET         0xCF40u

#endif
