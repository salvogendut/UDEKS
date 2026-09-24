/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/bench.h"

#define SOURCE ((volatile udeks_bench_u8 *)UDEKS_BENCH_WORK_SRC)
#define DESTINATION ((volatile udeks_bench_u8 *)UDEKS_BENCH_WORK_DST)

void bench_prepare(void)
{
    udeks_bench_u16 i;
    udeks_bench_u8 value = 0x5au;

    for (i = 0; i < 256u; ++i) {
        value = (udeks_bench_u8)((value << 1) ^
                ((value & 0x80u) != 0u ? 0x1du : 0u) ^
                (udeks_bench_u8)i);
        SOURCE[i] = value;
        DESTINATION[i] = 0u;
    }
}

udeks_bench_u16 bench_workload_empty(void)
{
    return 0xbeefu;
}

udeks_bench_u16 bench_workload_fill(void)
{
    udeks_bench_u16 i;
    udeks_bench_u16 sum = 0u;

    for (i = 0u; i < UDEKS_BENCH_BLOCK_SIZE; ++i) {
        DESTINATION[i] = 0x31u;
    }
    for (i = 0u; i < UDEKS_BENCH_BLOCK_SIZE; ++i) {
        sum = (udeks_bench_u16)(sum + DESTINATION[i]);
    }
    return sum;
}

udeks_bench_u16 bench_workload_copy(void)
{
    udeks_bench_u16 i;
    udeks_bench_u16 sum = 0u;

    for (i = 0u; i < UDEKS_BENCH_BLOCK_SIZE; ++i) {
        DESTINATION[i] = SOURCE[i];
    }
    for (i = 0u; i < UDEKS_BENCH_BLOCK_SIZE; ++i) {
        sum = (udeks_bench_u16)(sum + DESTINATION[i]);
    }
    return sum;
}

udeks_bench_u16 bench_workload_checksum(void)
{
    udeks_bench_u16 i;
    udeks_bench_u16 sum = 0u;

    for (i = 0u; i < UDEKS_BENCH_BLOCK_SIZE; ++i) {
        sum = (udeks_bench_u16)(sum + SOURCE[i]);
    }
    return sum;
}

udeks_bench_u16 bench_workload_control(void)
{
    udeks_bench_u16 i;
    udeks_bench_u16 state = 0xace1u;

    for (i = 0u; i < 128u; ++i) {
        switch ((udeks_bench_u8)state & 3u) {
        case 0u:
            state = (udeks_bench_u16)(state + i + 0x0101u);
            break;
        case 1u:
            state = (udeks_bench_u16)(state ^ (i << 3));
            break;
        case 2u:
            state = (udeks_bench_u16)((state >> 1) | (state << 15));
            break;
        default:
            state = (udeks_bench_u16)(state - i - 0x001du);
            break;
        }
    }
    return state;
}

udeks_bench_u16 bench_workload_arith16(void)
{
    udeks_bench_u16 i;
    udeks_bench_u16 value = 0x1357u;

    for (i = 0u; i < 64u; ++i) {
        value = (udeks_bench_u16)((value << 1) + 0x1234u);
        value = (udeks_bench_u16)(value ^ (i | (i << 8)));
    }
    return value;
}
