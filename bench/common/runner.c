/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/bench.h"

#define RESULT ((volatile udeks_bench_u8 *)UDEKS_BENCH_RESULT_BASE)

static void write_u16(udeks_bench_u8 offset, udeks_bench_u16 value)
{
    RESULT[offset] = (udeks_bench_u8)value;
    RESULT[(udeks_bench_u8)(offset + 1u)] = (udeks_bench_u8)(value >> 8);
}

static void write_record(udeks_bench_u8 index, udeks_bench_u8 case_id,
                         udeks_bench_u16 iterations, udeks_bench_u16 ticks,
                         udeks_bench_u16 checksum)
{
    udeks_bench_u8 offset = (udeks_bench_u8)(UDEKS_BENCH_HEADER_SIZE +
        index * UDEKS_BENCH_RECORD_SIZE);

    RESULT[offset] = case_id;
    RESULT[(udeks_bench_u8)(offset + 1u)] = 0u;
    write_u16((udeks_bench_u8)(offset + 2u), iterations);
    write_u16((udeks_bench_u8)(offset + 4u), ticks);
    write_u16((udeks_bench_u8)(offset + 6u), checksum);
}

#define RUN_CASE(index, id, iterations, expression) do { \
    udeks_bench_u16 value;                              \
    udeks_bench_u16 ticks;                              \
    bench_timer_start();                                \
    value = (expression);                               \
    ticks = bench_timer_elapsed();                      \
    write_record((index), (id), (iterations), ticks, value); \
} while (0)

void bench_run_suite(udeks_bench_u8 cpu_id)
{
    udeks_bench_u8 configuration = RESULT[6];

    RESULT[0] = 'B';
    RESULT[1] = 'M';
    RESULT[2] = 'R';
    RESULT[3] = 'K';
    RESULT[4] = UDEKS_BENCH_FORMAT_VERSION;
    RESULT[5] = cpu_id;
    RESULT[6] = configuration;
    RESULT[7] = UDEKS_BENCH_CASE_COUNT;
    RESULT[8] = UDEKS_BENCH_STATE_RUNNING;
    RESULT[9] = UDEKS_BENCH_RECORD_SIZE;
    RESULT[10] = UDEKS_BENCH_TIMER_CIA1_TB;
    RESULT[11] = 0u;
    write_u16(12u, 0u);
    write_u16(14u, 0u);

    bench_prepare();

    RUN_CASE(0u, UDEKS_BENCH_CASE_EMPTY, 1u, bench_workload_empty());
    RUN_CASE(1u, UDEKS_BENCH_CASE_FILL, 128u, bench_workload_fill());
    RUN_CASE(2u, UDEKS_BENCH_CASE_COPY, 128u, bench_workload_copy());
    RUN_CASE(3u, UDEKS_BENCH_CASE_CHECKSUM, 128u,
             bench_workload_checksum());
    RUN_CASE(4u, UDEKS_BENCH_CASE_CONTROL, 128u,
             bench_workload_control());
    RUN_CASE(5u, UDEKS_BENCH_CASE_ARITH16, 64u,
             bench_workload_arith16());

    RESULT[8] = UDEKS_BENCH_STATE_COMPLETE;
}
