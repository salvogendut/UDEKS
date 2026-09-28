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
