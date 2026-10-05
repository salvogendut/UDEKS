/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_RETAINED_PATHS_H
#define UDEKS_RETAINED_PATHS_H
/* Private graphics-service seam, not callable by disk programs. */
#define UDEKS_RETAINED_BASE 0x1300u
#define UDEKS_RETAINED_POOL_SIZE 2304u
#define UDEKS_RETAINED_CAPACITY 1280u
#define UDEKS_RETAINED_COMMANDS 160u
#define UDEKS_RETAINED_PATH_FLAG 0x8000u
extern unsigned int udeks_retained_lengths[4];
extern unsigned int udeks_graphics_origin_x;
extern unsigned char udeks_graphics_origin_y;
unsigned int __fastcall__ udeks_retained_address(unsigned char index);
unsigned char __fastcall__ udeks_retained_present(unsigned char index);
void __fastcall__ udeks_retained_discard(unsigned char index);
void __fastcall__ udeks_retained_read(unsigned int address);
void __fastcall__ udeks_retained_paths_paint(unsigned char index);
#endif
