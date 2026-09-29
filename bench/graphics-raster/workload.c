/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/vic_graphics.h"
#include "udeks/memory.h"

#define RESULT ((volatile unsigned char *)0x7FC0u)
#define ROWS ((unsigned int *)UDEKS_VIC_ROW_TABLE_BASE)
#define DIRTY ((unsigned char *)UDEKS_VIC_DIRTY_MAP_BASE)
#define CLIP ((int *)UDEKS_VIC_CLIP_STATE_BASE)
extern unsigned char udeks_vic_bitmap_shadow[UDEKS_VIC_BITMAP_SIZE];
extern void raster_timer_start(void);
extern void raster_timer_stop(void);

int main(void)
{
    unsigned int i;
    unsigned char n;
#if CASE == 0
    int x;
    int y;
#endif

    for (n = 0; n < 64u; ++n) RESULT[n] = 0;
    RESULT[0] = 'R'; RESULT[1] = 'A'; RESULT[2] = 'S'; RESULT[3] = 'T';
    RESULT[4] = 1; RESULT[5] = 1;
    RESULT[6] = VARIANT; RESULT[7] = CASE;
    for (i = 0; i < 200u; ++i) ROWS[i] = (i & 248u) * 40u + (i & 7u);
    for (i = 0; i < UDEKS_VIC_BITMAP_SIZE; ++i)
        udeks_vic_bitmap_shadow[i] = (unsigned char)(i * 13u + 7u);
    for (n = 0; n < 32u; ++n) DIRTY[n] = 0;
#if CASE == 3
    CLIP[0] = 49; CLIP[1] = 25; CLIP[2] = 271; CLIP[3] = 167;
#else
    CLIP[0] = 0; CLIP[1] = 0; CLIP[2] = 320; CLIP[3] = 200;
#endif
    raster_timer_start();
#if CASE == 0
    for (n = 0; n < 96u; ++n) {
        x = (n % 24u) * 11u + 10u;
        y = (n % 16u) * 9u + 10u;
        udeks_vic_bitmap_line(x, y, x + 17, y + 11, n & 1u);
    }
#elif CASE == 1
    for (n = 0; n < 24u; ++n)
        udeks_vic_bitmap_line(-20, n * 7u, 340, 190 - (int)n * 6, n & 1u);
#elif CASE == 2
    for (n = 0; n < 24u; ++n)
        udeks_vic_bitmap_fill(32, 40, 160, 80, n & 1u);
#elif CASE == 3
    for (n = 0; n < 24u; ++n)
        udeks_vic_bitmap_fill(-10 + (int)n * 7, 8u + n * 3u, 160, 90, n & 1u);
#endif
    raster_timer_stop();
    for (i = 0; i < UDEKS_VIC_BITMAP_SIZE; ++i) RESULT[64u + i] = udeks_vic_bitmap_shadow[i];
    for (n = 0; n < 32u; ++n) RESULT[8064u + n] = DIRTY[n];
    RESULT[5] = 2;
    return 0;
}
