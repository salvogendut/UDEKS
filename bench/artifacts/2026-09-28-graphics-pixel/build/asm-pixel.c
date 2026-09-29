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

