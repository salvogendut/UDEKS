/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_BENCH_H
#define UDEKS_BENCH_H

typedef unsigned char udeks_bench_u8;
typedef unsigned short udeks_bench_u16;

/* Both selected data models define char as 8 bits and short as 16 bits. */

#define UDEKS_BENCH_RESULT_BASE       0xF100u
#define UDEKS_BENCH_RESULT_SIZE       128u
#define UDEKS_BENCH_WORK_SRC          0xE000u
#define UDEKS_BENCH_WORK_DST          0xE100u
#define UDEKS_BENCH_BLOCK_SIZE        128u

#define UDEKS_BENCH_FORMAT_VERSION    1u
#define UDEKS_BENCH_CPU_8502          1u
#define UDEKS_BENCH_CPU_Z80           2u

#define UDEKS_BENCH_CONFIG_UNSPECIFIED 0u
#define UDEKS_BENCH_CONFIG_8502_1MHZ   1u
#define UDEKS_BENCH_CONFIG_8502_2MHZ   2u
#define UDEKS_BENCH_CONFIG_Z80_STOCK   3u

#define UDEKS_BENCH_STATE_RUNNING     1u
#define UDEKS_BENCH_STATE_COMPLETE    2u

#define UDEKS_BENCH_TIMER_CIA1_TB     1u

#define UDEKS_BENCH_CASE_EMPTY        1u
#define UDEKS_BENCH_CASE_FILL         2u
#define UDEKS_BENCH_CASE_COPY         3u
#define UDEKS_BENCH_CASE_CHECKSUM     4u
#define UDEKS_BENCH_CASE_CONTROL      5u
#define UDEKS_BENCH_CASE_ARITH16      6u
#define UDEKS_BENCH_CASE_COUNT        6u

#define UDEKS_BENCH_HEADER_SIZE       16u
#define UDEKS_BENCH_RECORD_SIZE       8u
#define UDEKS_BENCH_TICKS_OVERFLOW    0xFFFFu

void bench_timer_start(void);
udeks_bench_u16 bench_timer_elapsed(void);

void bench_prepare(void);
udeks_bench_u16 bench_workload_empty(void);
udeks_bench_u16 bench_workload_fill(void);
udeks_bench_u16 bench_workload_copy(void);
udeks_bench_u16 bench_workload_checksum(void);
udeks_bench_u16 bench_workload_control(void);
udeks_bench_u16 bench_workload_arith16(void);

void bench_run_suite(udeks_bench_u8 cpu_id);

#endif
