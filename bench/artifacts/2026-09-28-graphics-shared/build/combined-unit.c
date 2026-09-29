/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/vic_graphics.h"
#include "udeks/memory.h"
#include "udeks/pointer.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_VIC_GRAPHICS_STATUS_BASE + (offset)))

extern unsigned char udeks_vic_graphics_enable(void);
extern unsigned char udeks_vic_graphics_disable(void);
extern void udeks_vic_pointer_set_x(unsigned int x);
extern void udeks_vic_pointer_set_y(unsigned char y);
extern void udeks_vic_pointer_busy_tick(void);
extern void udeks_vic_bitmap_commit_page(unsigned char page);
extern void udeks_vic_bitmap_outline_blit(void);

#pragma bss-name(push, "VICSHADOW")
unsigned char udeks_vic_bitmap_shadow[UDEKS_VIC_BITMAP_SIZE];
#pragma bss-name(pop)

#define bitmap_rows ((unsigned int *)UDEKS_VIC_ROW_TABLE_BASE)
#define dirty_pages ((unsigned char *)UDEKS_VIC_DIRTY_MAP_BASE)
#define clip_left (*(int *)(UDEKS_VIC_CLIP_STATE_BASE + 0u))
#define clip_top (*(int *)(UDEKS_VIC_CLIP_STATE_BASE + 2u))
#define clip_right (*(int *)(UDEKS_VIC_CLIP_STATE_BASE + 4u))
#define clip_bottom (*(int *)(UDEKS_VIC_CLIP_STATE_BASE + 6u))

#define OUTLINE_COUNT          (*(volatile unsigned char *)0xF37Fu)
#define OUTLINE_BUFFER         ((volatile unsigned char *)0xF380u)
#define OUTLINE_RECORD_SIZE    15u

#define PLOT_UNCHECKED(plot_x, plot_y, plot_color) do { \
    pixel_offset = (unsigned int)(bitmap_rows[(unsigned char)(plot_y)] + \
        ((unsigned int)(plot_x) & 0xFFF8u)); \
    pixel_mask = (unsigned char)(0x80u >> ((unsigned int)(plot_x) & 7u)); \
    if ((plot_color) == UDEKS_VIC_COLOR_BLACK) { \
        udeks_vic_bitmap_shadow[pixel_offset] |= pixel_mask; \
    } else { \
        udeks_vic_bitmap_shadow[pixel_offset] &= \
            (unsigned char)~pixel_mask; \
    } \
    dirty_pages[pixel_offset >> 8] = 1; \
} while (0)

static unsigned int unsigned_magnitude(int value)
{
    return value < 0 ? (unsigned int)-value : (unsigned int)value;
}
void udeks_vic_bitmap_line(
    int x0, int y0, int x1, int y1, unsigned char color)
{
    static int dx;
    static int dy;
    static int error;
    static int twice;
    static int step_x;
    static int step_y;

    dx = (int)unsigned_magnitude(x1 - x0);
    dy = -(int)unsigned_magnitude(y1 - y0);
    step_x = x0 < x1 ? 1 : -1;
    step_y = y0 < y1 ? 1 : -1;
    error = dx + dy;
    for (;;) {
        udeks_vic_bitmap_pixel(x0, y0, color);
        if (x0 == x1 && y0 == y1) break;
        twice = error << 1;
        if (twice >= dy) {
            error += dy;
            x0 += step_x;
        }
        if (twice <= dx) {
            error += dx;
            y0 += step_y;
        }
    }
}
void udeks_vic_bitmap_rectangle(
    int x, int y, int width, int height, unsigned char color)
{
    int last_x;
    int last_y;
    if (width <= 0 || height <= 0) return;
    last_x = x + width - 1;
    last_y = y + height - 1;
    udeks_vic_bitmap_fill(x, y, width, 1, color);
    udeks_vic_bitmap_fill(x, last_y, width, 1, color);
    udeks_vic_bitmap_fill(x, y, 1, height, color);
    udeks_vic_bitmap_fill(last_x, y, 1, height, color);
}
/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Candidate fragment inserted into an isolated display-service translation
 * unit. Private serialized row parameters, not a new public or kernel ABI. */
unsigned int udeks_span_offset;
unsigned char udeks_span_count, udeks_span_first, udeks_span_last;
unsigned char udeks_span_color;
extern void udeks_span_fill_row(void);

void udeks_vic_bitmap_fill(
    int x, int y, int width, int height, unsigned char color)
{
    static int row;
    static int last_x;
    static int last_y;
    static unsigned int left;

    if (width <= 0 || height <= 0) return;
    last_x = x + width;
    last_y = y + height;
    if (x < clip_left) x = clip_left;
    if (y < clip_top) y = clip_top;
    if (last_x > clip_right) last_x = clip_right;
    if (last_y > clip_bottom) last_y = clip_bottom;
    if (x >= last_x || y >= last_y) return;
    left = (unsigned int)x;
    udeks_span_count = (unsigned char)(
        (((unsigned int)last_x - 1u) >> 3) - (left >> 3) + 1u);
    udeks_span_first = (unsigned char)(0xFFu >> (left & 7u));
    udeks_span_last = (unsigned char)~(0x7Fu >> ((last_x - 1) & 7u));
    udeks_span_color = color;
    left &= 0xFFF8u;
    for (row = y; row < last_y; ++row) {
        udeks_span_offset = bitmap_rows[(unsigned char)row] + left;
        udeks_span_fill_row();
    }
}
