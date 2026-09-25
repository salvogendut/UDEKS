/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/shell.h"

static unsigned char is_separator(unsigned char value)
{
    return value == ' ' || value == '\t';
}

unsigned char udeks_shell_tokenize(
    unsigned char *line, unsigned char *offsets,
    unsigned char capacity)
{
    unsigned char count;
    unsigned char position;

    count = 0;
    position = 0;
    for (;;) {
        while (is_separator(line[position])) {
            ++position;
        }
        if (line[position] == 0) {
            return count;
        }
        if (count == capacity) {
            return UDEKS_SHELL_PARSE_TOO_MANY;
        }
        offsets[count] = position;
        ++count;
        while (line[position] != 0 && !is_separator(line[position])) {
            ++position;
        }
        if (line[position] != 0) {
            line[position] = 0;
            ++position;
        }
    }
}
