/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private measured replacement; not linked by normal UDEKS. These twelve
 * HIGHBSS bytes belong to one serialized manager drawing step. No callbacks,
 * polls or IRQ drawing inside it; never overlay drag fields or cache guards.
 * Title/window pointers stay automatic and are not retained between steps.
 */
#pragma bss-name(push, "HIGHBSS")
static unsigned int chrome_x, chrome_width, chrome_right;
static unsigned char chrome_y, chrome_offset, chrome_character, chrome_bits, chrome_column, chrome_color;
#pragma bss-name(pop)
static void chrome_pixel(unsigned int at)
{
    udeks_vic_bitmap_pixel(at, chrome_y, UDEKS_VIC_COLOR_BLACK);
}
static void chrome_span(unsigned int at, unsigned int width)
{
    udeks_vic_bitmap_fill(at, chrome_y, width, 1, chrome_color);
}
static void draw_chrome_row(register const struct udeks_window *window,
    unsigned char row)
{
    const unsigned char *text;

    chrome_x = window->x;
    chrome_y = window->y + row;
    chrome_width = window->width;
    chrome_right = chrome_x + chrome_width - 1u;
    chrome_color = row == 0 || row == window->height - 1u ? UDEKS_VIC_COLOR_BLACK : UDEKS_VIC_COLOR_YELLOW;
    chrome_span(chrome_x, chrome_width);
    if (chrome_color != UDEKS_VIC_COLOR_BLACK) {
        chrome_pixel(chrome_x);
        chrome_pixel(chrome_right);
    }
    chrome_color = UDEKS_VIC_COLOR_BLACK;
    if (row >= 2u && row <= window->height - 3u) {
        if (row == 2u || row == window->height - 3u || row == UDEKS_WINDOW_TITLE_HEIGHT)
            chrome_span(chrome_x + 2u, chrome_width - 4u);
        else {
            chrome_pixel(chrome_x + 2u);
            chrome_pixel(chrome_right - 2u);
        }
    }
    if ((window->flags & UDEKS_WINDOW_FLAG_CLOSABLE) && row >= 3u && row <= 10u) {
        chrome_x = chrome_right - 11u;
        if (row == 3u || row == 10u)
            chrome_span(chrome_x, 8);
        else {
            chrome_pixel(chrome_x);
            chrome_pixel(chrome_x + 7u);
        }
        if (row >= 5u && row <= 8u) {
            chrome_pixel(chrome_x + row - 3u);
            chrome_pixel(chrome_x + 10u - row);
        }
    }
    if (window->flags & UDEKS_WINDOW_FLAG_RESIZABLE) {
        /* Valid height/row give -4..195. Converting negative values to a
         * byte gives 252..255, outside both stroke ranges. */
        chrome_offset = window->height - 5u - row;
        if (chrome_offset <= 6u)
            chrome_pixel(chrome_right - 10u + chrome_offset);
        if (chrome_offset <= 3u)
            chrome_pixel(chrome_right - 7u + chrome_offset);
    }
    if (row < 4u || row > 8u) return;
    text = window->title;
    chrome_x = window->x + 4u;
    chrome_right -= 13u;
    while (text && *text && chrome_x + 3u <= chrome_right) {
        chrome_character = *text++;
        if (chrome_character >= 'a' && chrome_character <= 'z') chrome_character -= 'a' - 'A';
        if (chrome_character >= 'A' && chrome_character <= 'Z') {
            chrome_bits = title_glyphs[chrome_character - 'A'][row - 4u];
            for (chrome_column = 0; chrome_column < 3u; ++chrome_column)
                if (chrome_bits & (4u >> chrome_column))
                    chrome_pixel(chrome_x + chrome_column);
        }
        chrome_x += 4u;
    }
}
