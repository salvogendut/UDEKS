/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private window-service overlay contract, not an application ABI. */
#ifndef UDEKS_WINDOW_CACHE_COMMAND_H
#define UDEKS_WINDOW_CACHE_COMMAND_H
#include "udeks/window_cache_state.h"

#define UDEKS_CACHE_COMMAND_INIT       0u
#define UDEKS_CACHE_COMMAND_INVALIDATE 1u
#define UDEKS_CACHE_COMMAND_CAPTURE    2u
#define UDEKS_CACHE_COMMAND_PASTE      3u
#define UDEKS_CACHE_COMMAND_STEP       4u
#define UDEKS_CACHE_COMMAND_READY      5u
#define UDEKS_CACHE_COMMAND_SUCCESS    0x80u
#define UDEKS_CACHE_COMMAND_WRITTEN    0x40u
#ifndef UDEKS_CACHE_IMAGE_CAPACITY
#define UDEKS_CACHE_IMAGE_CAPACITY     3072u
#endif

/* A STEP copies and acknowledges exactly one row while the caller holds the
 * gateway lease. It never calls an application, yields, or polls a service.
 * Owner/generation are checked on EVERY continuation, including STEP.
 * Capture eligibility is an explicit window-manager assertion, not inferred
 * from the application's private render counters. */
uint8_t __fastcall__ udeks_cache_overlay_command(uint8_t command);
#endif
