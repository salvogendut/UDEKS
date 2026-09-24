/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/bench.h"

void z80_main(void)
{
    bench_run_suite(UDEKS_BENCH_CPU_Z80);
}
