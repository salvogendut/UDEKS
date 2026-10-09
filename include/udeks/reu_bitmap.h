/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_REU_BITMAP_H
#define UDEKS_REU_BITMAP_H
#include "udeks/reu_store.h"
#define UDEKS_BITMAP_REU_STRIDE 128u
extern uint16_t udeks_bitmap_handles[4];
extern unsigned char udeks_bitmap_row_buffer[30], udeks_bitmap_row_stride;
extern unsigned int udeks_bitmap_row_offset;
void __fastcall__ udeks_bitmap_release_hidden(unsigned char index);
void __fastcall__ udeks_bitmap_release(unsigned char index);
unsigned char __fastcall__ udeks_bitmap_fetch_row(unsigned char index);
#endif
