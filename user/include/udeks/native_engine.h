/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_NATIVE_ENGINE_H
#define UDEKS_NATIVE_ENGINE_H
#include "udeks/native_console.h"
/* One synchronous request through engine/engreply. No caller pointers cross
 * IPC. WAVE count is 1..8; output/result remain untouched on every failure.
 * Endpoint contention is reported, never retried by creating another name.
 * Accepted work is not resent. Each transport wait is bounded to 600 sleeps.
 * Returns 0 or UDEKS_IO_ERROR with udeks_errno. Task-private, non-reentrant. */
unsigned char udeks_engine_wave(unsigned char phase,unsigned char step,
                               unsigned char count,unsigned char *samples,
                               unsigned int *next_phase);
unsigned char udeks_engine_nop(void);
unsigned char udeks_engine_stop(void);
#endif
