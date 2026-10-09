/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Same production translation unit; only MMIO is redirected for sim6502. */
#include "udeks/window.h"
unsigned char test_status[32];
#undef UDEKS_WINDOW_STATUS_BASE
#define UDEKS_WINDOW_STATUS_BASE ((unsigned int)test_status)
#define UDEKS_CACHE_MANAGER_HOST_TEST
#include "../../src/services/window/window_manager_cached.c"
