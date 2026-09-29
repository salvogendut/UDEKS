/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/kernel_bench.h"

void bench_main(void)
{
    kernel_run_suite(UDEKS_KERNEL_CPU_8502);
}
