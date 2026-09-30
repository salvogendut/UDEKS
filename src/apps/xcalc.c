/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/calc.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"

#define WIDTH 104u
#define HEIGHT 133u
static unsigned char handle;
static unsigned int wx, ww;
static unsigned char wy, wh;
static char display[12];
static unsigned char dirty;
/* Four columns, five rows. N is sign change; unused cells never act. */
static const unsigned char keys[] = "789/456*123-C0=+.N  ";
static const unsigned char glyphs[][5] = {
    {7,5,5,5,7},{2,6,2,2,7},{7,1,7,4,7},{7,1,7,1,7},
    {5,5,7,1,1},{7,4,7,1,7},{7,4,7,5,7},{7,1,1,1,1},
    {7,5,7,5,7},{7,5,7,1,7},
    {2,2,7,2,2},{0,0,7,0,0},{5,2,7,2,5},{1,1,2,4,4},
    {0,7,0,7,0},{3,4,4,4,3},{0,0,0,0,2},{2,7,2,0,7},
    {7,4,6,4,7}
};

static void glyph(unsigned int x, unsigned char y, unsigned char c)
{
    unsigned char i, r, b;
    const unsigned char *p;
    if (c >= '0' && c <= '9') i = c - '0';
    else {
        p = (const unsigned char *)"+-*/=C.NE";
        for (i = 0; p[i] && p[i] != c; ++i) {}
        if (!p[i]) return;
        i += 10;
    }
    for (r = 0; r < 5; ++r)
        for (b = 0; b < 3; ++b)
            if (glyphs[i][r] & (4u >> b))
                udeks_vic_bitmap_fill(x + b*2u, y + r*2u, 2, 2, 0);
}

static void draw_display(void)
{
    unsigned char i;
    udeks_calc_format(display);
    udeks_vic_bitmap_fill(wx+2u, wy+15u, 100, 15, 7);
    for (i=0; display[i]; ++i) glyph(wx+5u+i*8u, wy+17u, display[i]);
}

static void paint(unsigned char h)
{
    unsigned char i;
    udeks_window_get_geometry(h, &wx, &wy, &ww, &wh);
    draw_display();
    for (i=0; i<5; ++i)
        udeks_vic_bitmap_line(wx+2u+i*25u, wy+31u, wx+2u+i*25u, wy+131u, 0);
    for (i=0; i<6; ++i)
        udeks_vic_bitmap_line(wx+2u, wy+31u+i*20u, wx+102u, wy+31u+i*20u, 0);
    for (i=0; i<20; ++i) glyph(wx+11u+(i%4u)*25u, wy+36u+(i/4u)*20u, keys[i]);
}

static void closed(unsigned char h) { (void)h; handle=0; }
unsigned char udeks_xcalc_initialize(void) { handle=dirty=0; udeks_calc_reset(); return 0; }
unsigned char udeks_xcalc_start(void)
{
    if (handle) return 2;
    handle = udeks_window_create(3, 1,
        UDEKS_WINDOW_FLAG_MOVABLE | UDEKS_WINDOW_FLAG_CLOSABLE | UDEKS_WINDOW_FLAG_FIXED_SIZE,
        108, 30, WIDTH, HEIGHT, (const unsigned char *)"XCALC", paint, closed);
    return handle ? 0 : 1;
}
unsigned char udeks_xcalc_poll(void)
{
    const struct udeks_window_click *click;
    unsigned char i;
    if (handle && (click = udeks_window_take_click(handle)) != 0) {
        if (click->x>2u && click->x<102u && click->y>31u && click->y<131u) {
            i = (unsigned char)(((click->y-31u)/20u)*4u + (click->x-2u)/25u);
            if (keys[i] != ' ') {
                udeks_calc_key(keys[i]);
                dirty=1;
            }
        }
    }
    if (handle && dirty && udeks_window_begin_paint(handle)==0) {
        draw_display();
        udeks_window_end_paint();
        dirty=0;
    }
    return 0;
}
unsigned char udeks_xcalc_stop(void) { return handle ? udeks_window_destroy(handle) : 1; }
unsigned char udeks_xcalc_is_running(void) { return handle != 0; }
unsigned char udeks_xcalc_is_focused(void) { return udeks_window_is_focused(handle); }
