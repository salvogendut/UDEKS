/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Exercise the actual ASM on every alignment pair, plus full-width and
 * bottom-right rows. No banking; this gate is separate from transfer tests. */
#include "cache.h"
#define RESULT ((volatile unsigned char *)0x7FC0u)
#define SHADOW ((unsigned char *)0xA1E0u)
#define STAGE ((volatile unsigned char *)0xF400u)
#define COUNT (*(volatile unsigned char *)0xF382u)
extern unsigned int cache_row_offset;
extern unsigned char cache_row_shift, cache_row_next_count, cache_row_last_mask;
extern void cache_capture_row(void);
extern void cache_paste_row(void);
#pragma bss-name(push, "VICSHADOW")
unsigned char cache_probe_shadow[8000];
#pragma bss-name(pop)

static unsigned int row_offset(unsigned char y)
{
    return (unsigned int)(y / 8u) * 320u + (y % 8u);
}

static void run_row(unsigned int x, unsigned char y, unsigned int dx,
                    unsigned char dy, unsigned int width)
{
    unsigned int i;
    for (i = 0; i < 256u; ++i) STAGE[i] = 0xA5u;
    COUNT = (unsigned char)((width + 7u) / 8u);
    cache_row_offset = row_offset(y) + (x / 8u) * 8u;
    cache_row_shift = (unsigned char)(x % 8u);
    cache_row_next_count = (unsigned char)(39u - x / 8u);
    cache_row_last_mask = 255u;
    if (width % 8u) cache_row_last_mask = (unsigned char)~(0x7Fu >> (width % 8u - 1u));
    cache_capture_row();
    if (STAGE[COUNT] != 0xA5u) RESULT[7] = 1;
    /* Paste masks padding too, so final pixels alone would not prove the
     * captured packed format clears the unused tail bits. Check directly. */
    if ((STAGE[COUNT - 1u] & (unsigned char)~cache_row_last_mask) != 0)
        RESULT[7] = 3;
    cache_row_offset = row_offset(dy) + (dx / 8u) * 8u;
    cache_row_shift = (unsigned char)(dx % 8u);
    cache_paste_row();
    if (STAGE[COUNT] != 0xA5u) RESULT[7] = 2;
}

int main(void)
{
    unsigned int i;
    unsigned char sa, da;
    for (i = 0; i < 64u; ++i) RESULT[i] = 0;
    RESULT[0]='W'; RESULT[1]='R'; RESULT[2]='O'; RESULT[3]='W';
    RESULT[4]=1; RESULT[5]=1;
    *(volatile unsigned char *)0xF3FFu = 0x5Au;
    *(volatile unsigned char *)0xC120u = 0xA5u;
    for (i = 0; i < 8000u; ++i) SHADOW[i] = (unsigned char)(i * 13u + 7u);
    for (i = 0; i < 32u; ++i) ((unsigned char *)0xE190u)[i] = 0;
    for (sa = 0; sa < 8u; ++sa)
        for (da = 0; da < 8u; ++da) {
            run_row(sa, 128u, da, (unsigned char)(sa * 8u + da), 17u);
            ++RESULT[8];
        }
    run_row(0u, 129u, 0u, 64u, 320u); ++RESULT[8];
    run_row(319u, 199u, 319u, 199u, 1u); ++RESULT[8];
    RESULT[12]=*(volatile unsigned char *)0xF3FFu;
    RESULT[13]=*(volatile unsigned char *)0xC120u;
    for (i = 0; i < 8000u; ++i) RESULT[64u+i]=SHADOW[i];
    for (i = 0; i < 32u; ++i) RESULT[8064u+i]=((unsigned char *)0xE190u)[i];
    RESULT[5]=2;
    return 0;
}
