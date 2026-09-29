/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/kernel_bench.h"

void z80_main(void)
{
    kernel_run_suite(UDEKS_KERNEL_CPU_Z80);
}
