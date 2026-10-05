/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_BANKED_GRAPHICS_H
#define UDEKS_BANKED_GRAPHICS_H
/* UTRQ 0.9..0.12, op 23, fd/flags zero, exactly 24 bytes; see abi/window.md.
 * Commands are window-relative, eight bytes each, maximum 48 per image.
 * 0: fill x,y,w,h,color,0,0; 1: line x,y,x2,y2,color,0,0;
 * 2: 2x glyph x,y,five 3-bit scanlines. All pixels are client-clipped. */
#define UDEKS_GFX_CREATE 1u
#define UDEKS_GFX_PRESENT 2u
#define UDEKS_GFX_EVENT 3u
#define UDEKS_GFX_CLOSE 4u
#define UDEKS_GFX_PATHS 5u /* UTRQ 0.12: packed polylines; see window ABI */
#define UDEKS_GFX_COMMANDS 48u
#define UDEKS_NATIVE_CLIENTS 4u
extern const unsigned char udeks_native_base_pages[4];
extern const unsigned char udeks_native_stack_pages[4];
/* CREATE flags: choose exactly one sizing policy, plus MOVABLE/CLOSABLE. */
#define UDEKS_GFX_MOVABLE 2u
#define UDEKS_GFX_CLOSABLE 4u
#define UDEKS_GFX_RESIZABLE 8u /* requires UTRQ 0.10 */
#define UDEKS_GFX_FIXED_SIZE 16u
/* 0.10 EVENT request: handle, last width LE16, last height. Response:
 * state, click x LE16, click y, current width LE16, current height (7 bytes).
 * Only state is valid when CLOSED; click coordinates only for CLICK. */
#define UDEKS_GFX_CLOSED 0u
#define UDEKS_GFX_IDLE 1u
#define UDEKS_GFX_RESIZED 2u
#define UDEKS_GFX_CLICK 3u
unsigned char __fastcall__ udeks_banked_call(unsigned char selector);
void __fastcall__ udeks_banked_read(unsigned int address);
void __fastcall__ udeks_banked_write(unsigned int address);
/* Request payload is length + zero-padded 16-byte basename. On success the
 * service publishes selected (0..3) and owns a copy of the instance name. */
unsigned char udeks_banked_graphics_launch(void);
unsigned char __fastcall__ udeks_banked_graphics_exec(const unsigned char *name);
extern unsigned char udeks_banked_graphics_selected;
extern unsigned char udeks_banked_graphics_names[4][16]; /* bounded, zero padded */
unsigned char __fastcall__ udeks_banked_graphics_stop_name(const unsigned char *name);
unsigned char __fastcall__ udeks_banked_graphics_stop(unsigned char index);
unsigned char __fastcall__ udeks_banked_graphics_running(unsigned char index);
void udeks_banked_graphics_poll(void);
void udeks_banked_graphics_request(void);
#endif
