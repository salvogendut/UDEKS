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

unsigned char udeks_vic_graphics_start(void);
unsigned char udeks_vic_graphics_poll(void);
unsigned char udeks_vic_graphics_initialize(void);
unsigned char udeks_vic_graphics_shutdown(void);
unsigned char udeks_vic_graphics_is_active(void);
void udeks_vic_bitmap_clear(unsigned char color);
void udeks_vic_bitmap_pixel(int x, int y, unsigned char color);
void udeks_vic_bitmap_line(
    int x0, int y0, int x1, int y1, unsigned char color);
void udeks_vic_bitmap_rectangle(
    int x, int y, int width, int height, unsigned char color);
void udeks_vic_bitmap_fill(
    int x, int y, int width, int height, unsigned char color);
void udeks_vic_bitmap_commit(void);

#endif
