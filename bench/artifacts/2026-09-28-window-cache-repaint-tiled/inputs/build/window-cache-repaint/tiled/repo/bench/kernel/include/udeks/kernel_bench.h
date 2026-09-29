/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_KERNEL_BENCH_H
#define UDEKS_KERNEL_BENCH_H

typedef unsigned char udeks_kernel_u8;
typedef unsigned short udeks_kernel_u16;

#define UDEKS_KERNEL_RESULT_BASE       0xF180u
#define UDEKS_KERNEL_FORMAT_VERSION    1u
#define UDEKS_KERNEL_CPU_8502          1u
#define UDEKS_KERNEL_CPU_Z80           2u
#define UDEKS_KERNEL_STATE_RUNNING     1u
#define UDEKS_KERNEL_STATE_COMPLETE    2u
#define UDEKS_KERNEL_RECORD_SIZE       8u
#define UDEKS_KERNEL_HEADER_SIZE       16u
#define UDEKS_KERNEL_CASE_COUNT        7u

#define UDEKS_KERNEL_CASE_EMPTY        1u
#define UDEKS_KERNEL_CASE_SWITCH       2u
#define UDEKS_KERNEL_CASE_TABLE        3u
#define UDEKS_KERNEL_CASE_EVENT        4u
#define UDEKS_KERNEL_CASE_MMU          5u
#define UDEKS_KERNEL_CASE_CIA          6u
#define UDEKS_KERNEL_CASE_VDC          7u

void bench_timer_start(void);
udeks_kernel_u16 bench_timer_elapsed(void);

void kernel_workload_prepare(void);
udeks_kernel_u16 kernel_workload_empty(void);
udeks_kernel_u16 kernel_workload_switch_dispatch(void);
udeks_kernel_u16 kernel_workload_table_dispatch(void);
udeks_kernel_u16 kernel_workload_event_queue(void);
udeks_kernel_u16 kernel_bench_mmu(void);
udeks_kernel_u16 kernel_bench_cia(void);
udeks_kernel_u16 kernel_bench_vdc(void);

void kernel_run_suite(udeks_kernel_u8 cpu_id);

#endif
