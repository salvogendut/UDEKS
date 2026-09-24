/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/root_console.h"

static unsigned char cells
    [UDEKS_ROOT_CONSOLE_ROWS][UDEKS_ROOT_CONSOLE_ROW_STRIDE];
static unsigned char cursor_column;
static unsigned char cursor_row;
static unsigned char cursor_visible;

void udeks_root_console_reset(void)
{
    unsigned char row;
    unsigned char column;

    for (row = 0; row < UDEKS_ROOT_CONSOLE_ROWS; ++row) {
        for (column = 0; column < UDEKS_ROOT_CONSOLE_COLUMNS; ++column) {
            cells[row][column] = ' ';
        }
        cells[row][UDEKS_ROOT_CONSOLE_COLUMNS] = 0;
    }
    cursor_column = 0;
    cursor_row = 0;
    cursor_visible = 0;
}

unsigned char udeks_root_console_write_at(
    unsigned char column, unsigned char row, const unsigned char *text)
{
    if (column >= UDEKS_ROOT_CONSOLE_COLUMNS ||
        row >= UDEKS_ROOT_CONSOLE_ROWS) {
        return UDEKS_ROOT_CONSOLE_BOUNDS;
    }
    while (*text != 0 && column < UDEKS_ROOT_CONSOLE_COLUMNS) {
        cells[row][column] = *text;
        ++column;
        ++text;
    }
    return UDEKS_ROOT_CONSOLE_OK;
}

unsigned char udeks_root_console_set_cursor(
    unsigned char column, unsigned char row, unsigned char visible)
{
    if (column >= UDEKS_ROOT_CONSOLE_COLUMNS ||
        row >= UDEKS_ROOT_CONSOLE_ROWS) {
        return UDEKS_ROOT_CONSOLE_BOUNDS;
    }
    cursor_column = column;
    cursor_row = row;
    cursor_visible = visible != 0;
    return UDEKS_ROOT_CONSOLE_OK;
}

const unsigned char *udeks_root_console_row(unsigned char row)
{
    if (row >= UDEKS_ROOT_CONSOLE_ROWS) {
        row = 0;
    }
    return cells[row];
}

unsigned char udeks_root_console_cursor_column(void)
{
    return cursor_column;
}

unsigned char udeks_root_console_cursor_row(void)
{
    return cursor_row;
}

unsigned char udeks_root_console_cursor_visible(void)
{
    return cursor_visible;
}
