/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CONSOLE_H
#define UDEKS_CONSOLE_H

#define UDEKS_CONSOLE_STATUS_BASE       0xF070u
#define UDEKS_CONSOLE_STATUS_SIZE       24u

#define UDEKS_CONSOLE_STATE_STARTING    1u
#define UDEKS_CONSOLE_STATE_READY       2u
#define UDEKS_CONSOLE_STATE_ERROR       0x80u

/* Static service lifecycle entry used by the bring-up registry. */
unsigned char udeks_console_start(void);

#endif
