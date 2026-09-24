/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_PANIC_H
#define UDEKS_PANIC_H

#include "udeks/compiler.h"

#define UDEKS_PANIC_STATUS_BASE          0xF0B0u
#define UDEKS_PANIC_STATUS_SIZE          16u
#define UDEKS_PANIC_STATE_PUBLISHED      2u

#define UDEKS_PANIC_SERVICE_START_BASE   0x20u

void UDEKS_FASTCALL udeks_panic(unsigned char code);

#endif
