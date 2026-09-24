/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_FRAMEBUFFER_SURFACE_H
#define UDEKS_FRAMEBUFFER_SURFACE_H

void udeks_surface_reset(void);
unsigned char udeks_surface_plot(
    unsigned int x, unsigned char y, unsigned char set);
unsigned char udeks_surface_hline(
    unsigned int x, unsigned char y, unsigned int width, unsigned char set);
unsigned char udeks_surface_fill_rect(
    unsigned int x, unsigned char y, unsigned int width,
    unsigned int height, unsigned char set);
unsigned char udeks_surface_draw_char(
    unsigned int x, unsigned char y, unsigned char character);
unsigned char udeks_surface_draw_text(
    unsigned int x, unsigned char y, const unsigned char *text);
void udeks_surface_blit_packed(
    unsigned char x_byte, unsigned char y, unsigned char width_bytes,
    unsigned char height, const unsigned char *source);
unsigned char udeks_surface_dirty_span(
    unsigned char y, unsigned char start,
    unsigned char *first, unsigned char *last);
unsigned char udeks_surface_byte(unsigned int offset);
void udeks_surface_clean_span(
    unsigned char y, unsigned char first, unsigned char last);

#endif
