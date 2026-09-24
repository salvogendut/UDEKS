/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_FRAMEBUFFER_H
#define UDEKS_FRAMEBUFFER_H

#define UDEKS_FRAMEBUFFER_STATUS_BASE       0xF0E0u
#define UDEKS_FRAMEBUFFER_STATUS_SIZE       32u

#define UDEKS_FRAMEBUFFER_STATE_STARTING    1u
#define UDEKS_FRAMEBUFFER_STATE_READY       2u
#define UDEKS_FRAMEBUFFER_STATE_ERROR       0x80u

#define UDEKS_FRAMEBUFFER_STRIDE            80u
#define UDEKS_FRAMEBUFFER_HEIGHT            200u
#define UDEKS_FRAMEBUFFER_SIZE              16000u

#define UDEKS_SPLASH_WIDTH_BYTES            8u
#define UDEKS_SPLASH_HEIGHT                 64u
#define UDEKS_SPLASH_SIZE                   512u
#define UDEKS_SPLASH_X_BYTES                2u
#define UDEKS_SPLASH_Y                      12u

#define UDEKS_WORDMARK_WIDTH_BYTES         8u
#define UDEKS_WORDMARK_HEIGHT              21u
#define UDEKS_WORDMARK_SIZE                168u
#define UDEKS_WORDMARK_X_BYTES             2u
#define UDEKS_WORDMARK_Y                   82u

#define UDEKS_FRAMEBUFFER_OK                0u
#define UDEKS_FRAMEBUFFER_NOT_READY         1u
#define UDEKS_FRAMEBUFFER_BUSY              2u
#define UDEKS_FRAMEBUFFER_NOT_OWNER         3u
#define UDEKS_FRAMEBUFFER_IO_ERROR          4u

#define UDEKS_FRAMEBUFFER_API_BACKING       0x01u
#define UDEKS_FRAMEBUFFER_API_PRIMITIVES    0x02u
#define UDEKS_FRAMEBUFFER_API_TEXT          0x04u
#define UDEKS_FRAMEBUFFER_API_DIRTY_FLUSH   0x08u
#define UDEKS_FRAMEBUFFER_API_OWNERSHIP     0x10u
#define UDEKS_FRAMEBUFFER_API_RETAINED_TEXT 0x20u
#define UDEKS_FRAMEBUFFER_API_FLAGS         0x3Fu

unsigned char udeks_framebuffer_start(void);
unsigned char udeks_framebuffer_acquire(void);
unsigned char udeks_framebuffer_release(void);
unsigned char udeks_framebuffer_plot(
    unsigned int x, unsigned char y, unsigned char set);
unsigned char udeks_framebuffer_hline(
    unsigned int x, unsigned char y, unsigned int width, unsigned char set);
unsigned char udeks_framebuffer_fill_rect(
    unsigned int x, unsigned char y, unsigned int width,
    unsigned int height, unsigned char set);
unsigned char udeks_framebuffer_draw_char(
    unsigned int x, unsigned char y, unsigned char character);
unsigned char udeks_framebuffer_draw_text(
    unsigned int x, unsigned char y, const unsigned char *text);
unsigned char udeks_framebuffer_refresh_root_console(void);
unsigned char udeks_framebuffer_flush(void);

#endif
