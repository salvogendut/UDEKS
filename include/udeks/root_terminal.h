/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_ROOT_TERMINAL_H
#define UDEKS_ROOT_TERMINAL_H

#define UDEKS_ROOT_TERMINAL_STATUS_BASE  0xF150u
#define UDEKS_ROOT_TERMINAL_STATUS_SIZE  32u

#define UDEKS_ROOT_TERMINAL_STARTING     1u
#define UDEKS_ROOT_TERMINAL_READY        2u
#define UDEKS_ROOT_TERMINAL_ERROR        0x80u

#define UDEKS_ROOT_TERMINAL_OK           0u
#define UDEKS_ROOT_TERMINAL_DEPENDENCY   1u
#define UDEKS_ROOT_TERMINAL_RENDER       2u

unsigned char udeks_root_terminal_start(void);
unsigned char udeks_root_terminal_poll(void);

#endif
