/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/root_console.h"
#include "udeks/root_terminal.h"

int main(void)
{
    unsigned char row, column;
    for (row = 0; row < UDEKS_ROOT_CONSOLE_ROWS; ++row) {
        for (column = 0; column < UDEKS_ROOT_CONSOLE_COLUMNS; ++column) {
            udeks_root_console_reset();
            if (udeks_root_console_set_cursor(column, row, 0)) return 1;
            if (udeks_root_terminal_prompt()) return 2;
            if (udeks_root_console_cursor_column() != 9) return 3;
            if (udeks_root_console_cursor_row() !=
                (column && row < 20 ? row+1 : row)) return 4;
            if (!udeks_root_console_cursor_visible()) return 5;
        }
    }
    return 0;
}
