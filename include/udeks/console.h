/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CONSOLE_H
#define UDEKS_CONSOLE_H

#define UDEKS_CONSOLE_STATUS_BASE       0xF070u
#define UDEKS_CONSOLE_STATUS_SIZE       24u

#define UDEKS_CONSOLE_STATE_STARTING    1u
#define UDEKS_CONSOLE_STATE_READY       2u
#define UDEKS_CONSOLE_STATE_ERROR       0x80u

#define UDEKS_CONSOLE_OK                0u
#define UDEKS_CONSOLE_VDC_ERROR         1u

#define UDEKS_CONSOLE_COLUMNS           80u
#define UDEKS_CONSOLE_ROWS              25u
#define UDEKS_CONSOLE_ROOT_X            14u
#define UDEKS_CONSOLE_ROOT_Y            2u

#define UDEKS_CONSOLE_APP_XINIT         0x01u
#define UDEKS_CONSOLE_APP_XCLOCK        0x02u
#define UDEKS_CONSOLE_APP_XWAVE         0x04u

/* Static service lifecycle entry used by the bring-up registry. */
unsigned char udeks_console_start(void);
unsigned char udeks_console_poll(void);
unsigned char udeks_console_refresh_root(void);

#endif
