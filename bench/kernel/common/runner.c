/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/kernel_bench.h"

#define RESULT ((volatile udeks_kernel_u8 *)UDEKS_KERNEL_RESULT_BASE)

static void write_u16(udeks_kernel_u8 offset, udeks_kernel_u16 value)
{
    RESULT[offset] = (udeks_kernel_u8)value;
    RESULT[(udeks_kernel_u8)(offset + 1u)] = (udeks_kernel_u8)(value >> 8);
}

static void write_record(udeks_kernel_u8 index, udeks_kernel_u8 case_id,
                         udeks_kernel_u16 iterations, udeks_kernel_u16 ticks,
                         udeks_kernel_u16 checksum)
{
    udeks_kernel_u8 offset = (udeks_kernel_u8)(UDEKS_KERNEL_HEADER_SIZE +
        index * UDEKS_KERNEL_RECORD_SIZE);

    RESULT[offset] = case_id;
    RESULT[(udeks_kernel_u8)(offset + 1u)] = 0u;
    write_u16((udeks_kernel_u8)(offset + 2u), iterations);
    write_u16((udeks_kernel_u8)(offset + 4u), ticks);
    write_u16((udeks_kernel_u8)(offset + 6u), checksum);
}

#define RUN_CASE(index, id, iterations, expression) do { \
    udeks_kernel_u16 value;                              \
    udeks_kernel_u16 ticks;                              \
    bench_timer_start();                                 \
    value = (expression);                                \
    ticks = bench_timer_elapsed();                       \
    write_record((index), (id), (iterations), ticks, value); \
} while (0)

void kernel_run_suite(udeks_kernel_u8 cpu_id)
{
    udeks_kernel_u8 configuration = RESULT[6];

    RESULT[0] = 'K';
    RESULT[1] = 'P';
    RESULT[2] = 'R';
    RESULT[3] = 'M';
    RESULT[4] = UDEKS_KERNEL_FORMAT_VERSION;
    RESULT[5] = cpu_id;
    RESULT[6] = configuration;
    RESULT[7] = UDEKS_KERNEL_CASE_COUNT;
    RESULT[8] = UDEKS_KERNEL_STATE_RUNNING;
    RESULT[9] = UDEKS_KERNEL_RECORD_SIZE;
    RESULT[10] = 1u; /* CIA1 Timer B */
    RESULT[11] = 0u;
    write_u16(12u, 0u);
    write_u16(14u, 0u);

    kernel_workload_prepare();
    RUN_CASE(0u, UDEKS_KERNEL_CASE_EMPTY, 1u, kernel_workload_empty());
    RUN_CASE(1u, UDEKS_KERNEL_CASE_SWITCH, 128u,
             kernel_workload_switch_dispatch());
    RUN_CASE(2u, UDEKS_KERNEL_CASE_TABLE, 128u,
             kernel_workload_table_dispatch());
    RUN_CASE(3u, UDEKS_KERNEL_CASE_EVENT, 32u,
             kernel_workload_event_queue());
    RUN_CASE(4u, UDEKS_KERNEL_CASE_MMU, 128u, kernel_bench_mmu());
    RUN_CASE(5u, UDEKS_KERNEL_CASE_CIA, 128u, kernel_bench_cia());
    RUN_CASE(6u, UDEKS_KERNEL_CASE_VDC, 128u, kernel_bench_vdc());

    RESULT[8] = UDEKS_KERNEL_STATE_COMPLETE;
}
