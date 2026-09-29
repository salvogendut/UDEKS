/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Candidate shared-pixel line: retain C Bresenham state and stepping. */
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
