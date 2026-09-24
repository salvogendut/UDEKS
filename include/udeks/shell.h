/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_SHELL_H
#define UDEKS_SHELL_H

#define UDEKS_SHELL_STATUS_BASE          0xF170u
#define UDEKS_SHELL_STATUS_SIZE          24u

#define UDEKS_SHELL_STATE_STARTING       1u
#define UDEKS_SHELL_STATE_READY          2u
#define UDEKS_SHELL_STATE_ERROR          0x80u

#define UDEKS_SHELL_OK                   0u
#define UDEKS_SHELL_DEPENDENCY           1u
#define UDEKS_SHELL_INPUT                2u
#define UDEKS_SHELL_PROMPT               3u

#define UDEKS_SHELL_MAX_ARGUMENTS        8u
#define UDEKS_SHELL_PARSE_TOO_MANY       0xFFu

unsigned char udeks_shell_tokenize(
    unsigned char *line, unsigned char *offsets,
    unsigned char capacity);
unsigned char udeks_shell_start(void);
unsigned char udeks_shell_poll(void);
unsigned char udeks_shell_interrupt_foreground(void);

#endif
