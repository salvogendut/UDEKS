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

#define UDEKS_SPLASH_WIDTH_BYTES            20u
#define UDEKS_SPLASH_HEIGHT                 160u
#define UDEKS_SPLASH_SIZE                   3200u
#define UDEKS_SPLASH_X_BYTES                30u
#define UDEKS_SPLASH_Y                      20u

unsigned char udeks_framebuffer_start(void);

#endif
