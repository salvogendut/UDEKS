/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_BANKED_GRAPHICS_H
#define UDEKS_BANKED_GRAPHICS_H
/* UTRQ 0.9, op 23, fd/flags zero, exactly 24 bytes; see abi/window.md.
 * Commands are window-relative, eight bytes each, maximum 48 per image.
 * 0: fill x,y,w,h,color,0,0; 1: line x,y,x2,y2,color,0,0;
 * 2: 2x glyph x,y,five 3-bit scanlines. All pixels are client-clipped. */
#define UDEKS_GFX_CREATE 1u
#define UDEKS_GFX_PRESENT 2u
#define UDEKS_GFX_EVENT 3u
#define UDEKS_GFX_CLOSE 4u
#define UDEKS_GFX_COMMANDS 48u
unsigned char __fastcall__ udeks_banked_call(unsigned char selector);
void __fastcall__ udeks_banked_read(unsigned int address);
void __fastcall__ udeks_banked_write(unsigned int address);
/* Private service selectors: 0 calculator/task 3, 1 drawing/task 4. */
unsigned char __fastcall__ udeks_banked_graphics_start(unsigned char index);
unsigned char __fastcall__ udeks_banked_graphics_stop(unsigned char index);
unsigned char __fastcall__ udeks_banked_graphics_running(unsigned char index);
void udeks_banked_graphics_poll(void);
void udeks_banked_graphics_request(void);
#endif
