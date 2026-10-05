/* SPDX-License-Identifier: GPL-3.0-or-later */
/* XSPRDEF: edit the eight hardware sprites. The list screen shows eight
 * numbered buttons; the editor magnifies one sprite so one 8x8 cell is one
 * sprite pixel. Clicking a cell toggles the pixel; S asks to save the working
 * copy into the session bank, B returns to the list. Windowed clients are
 * click-only and have no file access, so save is session-in-app for now. */
#include "udeks/banked_graphics.h"
#define R ((volatile unsigned char *)0xf359)
#define P ((volatile unsigned char *)0xf367)
extern unsigned char __fastcall__ gfx_request(unsigned char op);
extern void gfx_sleep(void);

#define SPRITES      8
#define SPRITE_BYTES 63
#define CELL         8
#define MAX_COMMANDS 72
#define MAG_X        8
#define MAG_Y        20
#define BTN_S_X      208
#define BTN_S_Y      56
#define BTN_B_X      208
#define BTN_B_Y      86
#define LIST_Y       80
#define LIST_STEP    34

static unsigned char handle;
static unsigned char sprite_bank[SPRITES][SPRITE_BYTES];
static unsigned char edit[SPRITE_BYTES];
static unsigned char commands[MAX_COMMANDS][8];
static unsigned char count;
static unsigned char mode;       /* 0 list, 1 editor */
static unsigned char selected;
static unsigned char confirming;

/* 3x5 glyphs, one byte per row, low three bits. */
static const unsigned char glyphs[][5] = {
    {7,5,5,5,7},{2,6,2,2,7},{7,1,7,4,7},{7,1,7,1,7},{5,5,7,1,1},
    {7,4,7,1,7},{7,4,7,5,7},{7,1,1,1,1},{7,5,7,5,7},{7,5,7,1,7},
    {2,5,7,5,5},{6,5,6,5,6},{7,4,6,4,7},{7,2,2,2,7},{5,6,4,6,5},
    {5,7,5,5,5},{2,5,5,5,2},{6,5,6,4,4},{6,5,6,5,5},{3,4,2,1,6},
    {7,2,2,2,2},{5,5,5,5,2},{5,5,2,2,2},{6,1,2,0,2}
};
#define GLYPH_TEXT "0123456789ABEIKNOPRSTVY?"

static const unsigned char row3[21] = {
    0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57, 60
};
static const unsigned char bit_mask[8] = { 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01 };

static unsigned char bit_get(const unsigned char *s, unsigned char x, unsigned char y)
{
    unsigned char value = s[(unsigned char)(row3[y] + (x >> 3))];
    return (unsigned char)((value & bit_mask[x & 7u]) ? 1u : 0u);
}
static void bit_flip(unsigned char *s, unsigned char x, unsigned char y)
{
    unsigned char index = (unsigned char)(row3[y] + (x >> 3));
    unsigned char mask = bit_mask[x & 7u];
    if (s[index] & mask) s[index] = (unsigned char)(s[index] & (unsigned char)(0xffu - mask));
    else s[index] = (unsigned char)(s[index] | mask);
}

static void fill(unsigned char x, unsigned char y, unsigned char w, unsigned char h,
    unsigned char color)
{
    unsigned char *c;
    if (count == MAX_COMMANDS) return;
    c = commands[count++];
    c[0] = 0; c[1] = x; c[2] = y; c[3] = w; c[4] = h; c[5] = color; c[6] = 0; c[7] = 0;
}
static void glyph(unsigned char x, unsigned char y, unsigned char ch)
{
    unsigned char i, row;
    unsigned char *c;
    for (i = 0; GLYPH_TEXT[i] && GLYPH_TEXT[i] != ch; ++i) {}
    if (!GLYPH_TEXT[i] || count == MAX_COMMANDS) return;
    c = commands[count++];
    c[0] = 2; c[1] = x; c[2] = y;
    for (row = 0; row < 5; ++row) c[3 + row] = glyphs[i][row];
}
static void text(unsigned char x, unsigned char y, const char *s)
{
    while (*s) { glyph(x, y, *s++); x = (unsigned char)(x + 7u); }
}

/* Emit the set pixels of a 63-byte sprite as merged rectangles, one 8x8 cell
 * per sprite pixel. */
static void emit_sprite(const unsigned char *s, unsigned char ox, unsigned char oy)
{
    unsigned char px[8], pw[8], py[8], pn;
    unsigned char nx[8], nw[8], ny[8];
    unsigned char rx[8], rw[8], used[8];
    unsigned char x, y, i, j, n, c, k;
    pn = 0;
    for (y = 0; y < 21u; ++y) {
        c = 0; x = 0;
        while (x < 24u) {
            while (x < 24u && !bit_get(s, x, y)) ++x;
            if (x == 24u) break;
            rx[c] = x;
            while (x < 24u && bit_get(s, x, y)) ++x;
            rw[c] = (unsigned char)(x - rx[c]);
            if (++c == 8u) break;
        }
        for (i = 0; i < c; ++i) used[i] = 0;
        n = 0;
        for (j = 0; j < pn; ++j) {
            for (i = 0; i < c; ++i)
                if (!used[i] && rx[i] == px[j] && rw[i] == pw[j]) break;
            if (i < c) {
                used[i] = 1;
                nx[n] = px[j]; nw[n] = pw[j]; ny[n] = py[j]; ++n;
            } else {
                fill((unsigned char)(ox + px[j] * CELL), (unsigned char)(oy + py[j] * CELL),
                    (unsigned char)(pw[j] * CELL), (unsigned char)((y - py[j]) * CELL), 0);
            }
        }
        for (i = 0; i < c; ++i) if (!used[i]) {
            nx[n] = rx[i]; nw[n] = rw[i]; ny[n] = y; ++n;
        }
        for (k = 0; k < n; ++k) { px[k] = nx[k]; pw[k] = nw[k]; py[k] = ny[k]; }
        pn = n;
    }
    for (j = 0; j < pn; ++j)
        fill((unsigned char)(ox + px[j] * CELL), (unsigned char)(oy + py[j] * CELL),
            (unsigned char)(pw[j] * CELL), (unsigned char)((21u - py[j]) * CELL), 0);
}

static void payload(void)
{
    unsigned char i;
    for (i = 0; i < 24u; ++i) P[i] = 0;
    P[1] = handle;
}
static unsigned char present(void)
{
    payload();
    P[2] = (unsigned char)((unsigned int)commands);
    P[3] = (unsigned char)((unsigned int)commands >> 8);
    P[4] = count;
    return gfx_request(UDEKS_GFX_PRESENT);
}
static unsigned char list_present(void)
{
    unsigned char i;
    count = 0;
    for (i = 0; i < SPRITES; ++i)
        glyph((unsigned char)(40u + i * LIST_STEP), LIST_Y, (unsigned char)('1' + i));
    return present();
}
static unsigned char editor_present(void)
{
    count = 0;
    emit_sprite(edit, MAG_X, MAG_Y);
    if (confirming) {
        text(BTN_S_X, 120, "SAVE? S/B");
    } else {
        glyph(BTN_S_X, BTN_S_Y, 'S');
        glyph(BTN_B_X, BTN_B_Y, 'B');
    }
    return present();
}
static void copy_sprite(unsigned char *dst, const unsigned char *src)
{
    unsigned char i;
    for (i = 0; i < SPRITE_BYTES; ++i) dst[i] = src[i];
}

unsigned char udeks_graphical_main(void)
{
    unsigned char i, x, y;
    payload(); P[1] = 0; P[3] = 0; P[4] = 320; P[5] = 200; P[6] = 0x16;
    for (i = 0; i < 7u; ++i) P[7 + i] = "XSPRDEF"[i];
    if (gfx_request(UDEKS_GFX_CREATE)) return 1;
    handle = R[11];
    mode = 0; confirming = 0;
    if (list_present()) return 2;
    for (;;) {
        payload(); if (gfx_request(UDEKS_GFX_EVENT)) return 3;
        if (!P[0]) return 0;
        if ((P[0] & 2u) && !P[2]) {
            x = P[1]; y = P[3];
            if (mode == 0) {
                for (i = 0; i < SPRITES; ++i) {
                    unsigned char bx = (unsigned char)(40u + i * LIST_STEP);
                    if (x >= (unsigned char)(bx - 4u) && x < (unsigned char)(bx + 10u) &&
                        y >= (unsigned char)(LIST_Y - 4u) && y < (unsigned char)(LIST_Y + 14u)) {
                        selected = i;
                        copy_sprite(edit, sprite_bank[i]);
                        mode = 1; confirming = 0;
                        break;
                    }
                }
                if (i == SPRITES) { gfx_sleep(); continue; }
                if (editor_present()) return 4;
            } else if (x >= MAG_X && x < (unsigned char)(MAG_X + 24u * CELL) &&
                       y >= MAG_Y && y < (unsigned char)(MAG_Y + 21u * CELL)) {
                bit_flip(edit, (unsigned char)((x - MAG_X) / CELL),
                    (unsigned char)((y - MAG_Y) / CELL));
                if (editor_present()) return 4;
            } else if (x >= (unsigned char)(BTN_S_X - 4u) && x < (unsigned char)(BTN_S_X + 12u) &&
                       y >= (unsigned char)(BTN_S_Y - 4u) && y < (unsigned char)(BTN_S_Y + 14u)) {
                if (confirming) {
                    copy_sprite(sprite_bank[selected], edit);
                    mode = 0; confirming = 0;
                    if (list_present()) return 4;
                } else {
                    confirming = 1;
                    if (editor_present()) return 4;
                }
            } else if (x >= (unsigned char)(BTN_B_X - 4u) && x < (unsigned char)(BTN_B_X + 12u) &&
                       y >= (unsigned char)(BTN_B_Y - 4u) && y < (unsigned char)(BTN_B_Y + 14u)) {
                if (confirming) {
                    confirming = 0;
                    if (editor_present()) return 4;
                } else {
                    mode = 0;
                    if (list_present()) return 4;
                }
            } else {
                gfx_sleep(); continue;
            }
        }
        gfx_sleep();
    }
}
