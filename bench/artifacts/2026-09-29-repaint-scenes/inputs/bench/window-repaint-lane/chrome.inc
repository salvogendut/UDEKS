/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private manager fragment, not linked into normal UDEKS. Valid window/table
 * lifetime and clipping are the driver's responsibility. No pointers persist.
 * One opaque row, at most 320 pixels wide, <=250 pixel calls, <=3 row fills.
 * Caller validates a work ticket, sets its clip, calls once, resets the clip
 * and acknowledges. No full-window replay under a one-row clip.
 */
static void draw_chrome_row(register const struct udeks_window *window,
    unsigned char row)
{
    int x = window->x;
    int y = window->y + row;
    int width = window->width;
    int right = x + width - 1;
    int offset;
    const unsigned char *text;
    unsigned char character, bits, column;

    udeks_vic_bitmap_fill(x, y, width, 1, UDEKS_VIC_COLOR_YELLOW);
    if (row == 0 || row == window->height - 1u)
        udeks_vic_bitmap_fill(x, y, width, 1, UDEKS_VIC_COLOR_BLACK);
    else {
        udeks_vic_bitmap_pixel(x, y, UDEKS_VIC_COLOR_BLACK);
        udeks_vic_bitmap_pixel(right, y, UDEKS_VIC_COLOR_BLACK);
    }
    if (row >= 2u && row <= window->height - 3u) {
        if (row == 2u || row == window->height - 3u || row == UDEKS_WINDOW_TITLE_HEIGHT)
            udeks_vic_bitmap_fill(x + 2, y, width - 4, 1, UDEKS_VIC_COLOR_BLACK);
        else {
            udeks_vic_bitmap_pixel(x + 2, y, UDEKS_VIC_COLOR_BLACK);
            udeks_vic_bitmap_pixel(right - 2, y, UDEKS_VIC_COLOR_BLACK);
        }
    }
    if ((window->flags & UDEKS_WINDOW_FLAG_CLOSABLE) && row >= 3u && row <= 10u) {
        offset = right - 11;
        if (row == 3u || row == 10u)
            udeks_vic_bitmap_fill(offset, y, 8, 1, UDEKS_VIC_COLOR_BLACK);
        else {
            udeks_vic_bitmap_pixel(offset, y, UDEKS_VIC_COLOR_BLACK);
            udeks_vic_bitmap_pixel(offset + 7, y, UDEKS_VIC_COLOR_BLACK);
        }
        if (row >= 5u && row <= 8u) {
            udeks_vic_bitmap_pixel(offset + row - 3, y, UDEKS_VIC_COLOR_BLACK);
            udeks_vic_bitmap_pixel(offset + 10 - row, y, UDEKS_VIC_COLOR_BLACK);
        }
    }
    if (window->flags & UDEKS_WINDOW_FLAG_RESIZABLE) {
        offset = (int)window->height - 5 - row;
        if (offset >= 0 && offset <= 6)
            udeks_vic_bitmap_pixel(right - 10 + offset, y, UDEKS_VIC_COLOR_BLACK);
        if (offset >= 0 && offset <= 3)
            udeks_vic_bitmap_pixel(right - 7 + offset, y, UDEKS_VIC_COLOR_BLACK);
    }
    if (row < 4u || row > 8u) return;
    text = window->title;
    x += 4;
    right -= 13;
    while (text && *text && x + 3 <= right) {
        character = *text++;
        if (character >= 'a' && character <= 'z') character -= 'a' - 'A';
        if (character >= 'A' && character <= 'Z') {
            bits = title_glyphs[character - 'A'][row - 4u];
            for (column = 0; column < 3u; ++column)
                if (bits & (4u >> column))
                    udeks_vic_bitmap_pixel(x + column, y, UDEKS_VIC_COLOR_BLACK);
        }
        x += 4;
    }
}
