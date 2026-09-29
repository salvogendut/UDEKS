/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_VIC_GRAPHICS_H
#define UDEKS_VIC_GRAPHICS_H

#define UDEKS_VIC_GRAPHICS_STATUS_BASE       0xF1B0u
#define UDEKS_VIC_GRAPHICS_STATUS_SIZE       24u

#define UDEKS_VIC_GRAPHICS_STARTING          1u
#define UDEKS_VIC_GRAPHICS_READY             2u
#define UDEKS_VIC_GRAPHICS_ACTIVE            3u
#define UDEKS_VIC_GRAPHICS_ERROR             0x80u

#define UDEKS_VIC_GRAPHICS_OK                0u
#define UDEKS_VIC_GRAPHICS_NOT_READY         1u
#define UDEKS_VIC_GRAPHICS_SETUP_FAILED      2u

#define UDEKS_VIC_GRAPHICS_MODE_HIRES        1u
#define UDEKS_VIC_COLOR_BLACK                0u
#define UDEKS_VIC_COLOR_YELLOW               7u

#define UDEKS_VIC_WIDTH                      320u
#define UDEKS_VIC_HEIGHT                     200u
#define UDEKS_VIC_BITMAP_SIZE                8000u
#define UDEKS_VIC_BITMAP_PAGES               32u

#define UDEKS_VIC_BUSY_Z80                   1u
#define UDEKS_VIC_BUSY_REPAINT               2u

unsigned char udeks_vic_graphics_start(void);
unsigned char udeks_vic_graphics_poll(void);
unsigned char udeks_vic_graphics_initialize(void);
unsigned char udeks_vic_graphics_shutdown(void);
unsigned char udeks_vic_graphics_is_active(void);
void udeks_vic_pointer_busy_begin(unsigned char owner);
void udeks_vic_pointer_busy_end(unsigned char owner);
void udeks_vic_bitmap_clear(unsigned char color);
void udeks_vic_bitmap_pixel(int x, int y, unsigned char color);
void udeks_vic_bitmap_line(
    int x0, int y0, int x1, int y1, unsigned char color);
void udeks_vic_bitmap_rectangle(
    int x, int y, int width, int height, unsigned char color);
void udeks_vic_bitmap_fill(
    int x, int y, int width, int height, unsigned char color);
void udeks_vic_bitmap_set_clip(int x, int y, int width, int height);
void udeks_vic_bitmap_reset_clip(void);
void udeks_vic_bitmap_outline_toggle(
    unsigned int x, unsigned char y,
    unsigned int width, unsigned char height);
void udeks_vic_bitmap_outline_move(
    unsigned int old_x, unsigned char old_y,
    unsigned int new_x, unsigned char new_y,
    unsigned int width, unsigned char height);
void udeks_vic_bitmap_commit(void);

#endif
