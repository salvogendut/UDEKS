/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_RETAINED_BITMAP_H
#define UDEKS_RETAINED_BITMAP_H
#include "udeks/bitmap_store.h"
/* Private fixed-pool binding behind UTRQ 0.20 graphics operations 8..11.
 * Adapter authenticates task/window and calls with a stable request record.
 * Renderer borrows the current clip and never calls back into the allocator. */
unsigned char __fastcall__ udeks_retained_bitmap_request(unsigned char index);
void __fastcall__ udeks_retained_bitmap_paint(unsigned char index);
#endif
