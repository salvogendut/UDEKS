/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_USER_SHELL_H
#define UDEKS_USER_SHELL_H

#define UDEKS_SHELL_MAX_ARGUMENTS        8u
#define UDEKS_SHELL_PARSE_TOO_MANY       0xFFu

unsigned char udeks_shell_tokenize(
    unsigned char *line, unsigned char *offsets,
    unsigned char capacity);

#endif
