/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Candidate rectangle: four clipped spans, no change to inclusive edges. */
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
