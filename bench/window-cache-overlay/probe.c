/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Diagnostic-only row driver, NOT a production cache continuation. */
#define RESULT ((volatile unsigned char *)0x7FC0u)
#define SHADOW ((unsigned char *)0xA1E0u)
#define PARAM ((volatile unsigned char *)0xF780u)
#define WORD(offset) (*(volatile unsigned int *)(0xF780u + (offset)))
extern void overlay_install(void), overlay_row(void);
extern void overlay_irq_start(void), overlay_irq_stop(void);
extern void overlay_flags_probe(void), overlay_guards(void);
extern unsigned int overlay_irq_count;
extern unsigned char overlay_irq_bad, overlay_flag_failure;
extern unsigned char overlay_stack_failure;
#pragma bss-name(push, "VICSHADOW")
unsigned char overlay_shadow[8000];
#pragma bss-name(pop)

static void parameters(unsigned int x, unsigned char y,
                       unsigned int width, unsigned int address,
                       unsigned char mode)
{
    WORD(0) = (unsigned int)(y / 8u) * 320u + (y % 8u) + (x & 0xFFF8u);
    WORD(2) = address;
    PARAM[4] = (unsigned char)((width + 7u) / 8u);
    PARAM[5] = (unsigned char)((width + (x & 7u) + 7u) / 8u);
    PARAM[6] = (unsigned char)(x & 7u);
    PARAM[7] = (width & 7u) ? (unsigned char)~(0x7Fu >> ((width & 7u) - 1u)) : 255u;
    PARAM[8] = mode;
}

static void row_guards(void)
{
    if (*(volatile unsigned char *)0xF7AFu != 0x5Au ||
        *(volatile unsigned char *)0xF7D8u != 0xA5u ||
        *(volatile unsigned char *)0xFF00u != 0x3Eu)
        RESULT[7] = 2;
}

static void protected_bytes(void)
{
    unsigned int i;
    for (i = 0; i < 736u; ++i)
        if (((volatile unsigned char *)0xF3A0u)[i] !=
                (i == 0x4Du ? 0 : (unsigned char)(i * 7u + 3u)))
            RESULT[7] = 1;
    row_guards();
}

static void move_image(unsigned int x, unsigned char y,
                       unsigned int dx, unsigned char dy,
                       unsigned int width, unsigned char height)
{
    unsigned int address, i;
    unsigned char row, stride;
    stride = (unsigned char)((width + 7u) / 8u);
    address = 0x4400u;
    for (row = 0; row < height; ++row) {
        parameters(x, (unsigned char)(y + row), width, address, 0);
        overlay_row();
        if ((PARAM[9] & (unsigned char)~PARAM[7]) != 0) RESULT[7] = 3;
        address += stride;
        row_guards();
        ++*(volatile unsigned int *)0x7FC8u;
    }
#if CASE == 1
    for (i = 0; i < 8000u; ++i) SHADOW[i] = (unsigned char)(i * 31u + 19u);
#else
    (void)i;
#endif
    address = 0x4400u;
    for (row = 0; row < height; ++row) {
        parameters(dx, (unsigned char)(dy + row), width, address, 1);
        overlay_row();
        address += stride;
        row_guards();
        ++*(volatile unsigned int *)0x7FC8u;
    }
}

int main(void)
{
    unsigned int i;
    unsigned char sa, da;
    for (i = 0; i < 64u; ++i) RESULT[i] = 0;
    RESULT[0] = 'O'; RESULT[1] = 'R'; RESULT[2] = 'O'; RESULT[3] = 'W';
    RESULT[4] = 1; RESULT[5] = 1; RESULT[6] = CASE;
    *(volatile unsigned char *)0xD501u = 0x3Eu;
    *(volatile unsigned char *)0xD504u = 0x7Fu;
    overlay_install();
    for (i = 0; i < 736u; ++i)
        ((volatile unsigned char *)0xF3A0u)[i] = (unsigned char)(i * 7u + 3u);
    *(volatile unsigned char *)0xF7AFu = 0x5Au;
    *(volatile unsigned char *)0xF7D8u = 0xA5u;
    for (i = 0; i < 8000u; ++i) SHADOW[i] = (unsigned char)(i * 13u + 7u);
    for (i = 0; i < 32u; ++i) ((unsigned char *)0xE190u)[i] = 0;
    parameters(0, 128, 17, 0x4400, 0);
    overlay_irq_start();
    overlay_flags_probe();
#if CASE == 0
    for (sa = 0; sa < 8u; ++sa)
        for (da = 0; da < 8u; ++da) {
            move_image(sa, 128, da, (unsigned char)(sa * 8u + da), 17, 1);
            ++RESULT[10];
        }
    move_image(0, 129, 0, 64, 320, 1); ++RESULT[10];
    move_image(319, 199, 319, 199, 1, 1); ++RESULT[10];
#else
    (void)sa; (void)da;
    move_image(7, 7, 100, 40, 220, 160); ++RESULT[10];
#endif
    overlay_irq_stop();
    RESULT[12] = (unsigned char)overlay_irq_count;
    RESULT[13] = (unsigned char)(overlay_irq_count >> 8);
    RESULT[14] = overlay_irq_bad;
    RESULT[15] = overlay_flag_failure;
    RESULT[18] = overlay_stack_failure;
    protected_bytes();
#if CASE == 0
    WORD(10) = 0x4428u;
#else
    WORD(10) = 0x5580u;
#endif
    overlay_guards();
    for (i = 0; i < 8000u; ++i) RESULT[64u + i] = SHADOW[i];
    for (i = 0; i < 32u; ++i) RESULT[8064u + i] = ((unsigned char *)0xE190u)[i];
    RESULT[5] = 2;
    return 0;
}
