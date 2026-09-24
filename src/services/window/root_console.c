/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/root_console.h"

/* Stage 1 has vacated this linker-owned low-RAM segment before kernel_main. */
#pragma bss-name(push, "LOWBSS")
static unsigned char cells
    [UDEKS_ROOT_CONSOLE_ROWS][UDEKS_ROOT_CONSOLE_ROW_STRIDE];
static unsigned char cursor_column;
static unsigned char cursor_row;
static unsigned char cursor_visible;
static unsigned char dirty_rows[UDEKS_ROOT_CONSOLE_ROWS];
static unsigned char dirty_first[UDEKS_ROOT_CONSOLE_ROWS];
static unsigned char dirty_last[UDEKS_ROOT_CONSOLE_ROWS];
#pragma bss-name(pop)

static void mark_cell_dirty(unsigned char row, unsigned char column)
{
    if (dirty_rows[row] == 0) {
        dirty_rows[row] = 1;
        dirty_first[row] = column;
        dirty_last[row] = column;
    } else {
        if (column < dirty_first[row]) {
            dirty_first[row] = column;
        }
        if (column > dirty_last[row]) {
            dirty_last[row] = column;
        }
    }
}

static void mark_all_dirty(void)
{
    unsigned char row;

    for (row = 0; row < UDEKS_ROOT_CONSOLE_ROWS; ++row) {
        dirty_rows[row] = 1;
        dirty_first[row] = 0;
        dirty_last[row] = UDEKS_ROOT_CONSOLE_COLUMNS - 1u;
    }
}

static void mark_cursor_dirty(void)
{
    if (cursor_visible != 0) {
        mark_cell_dirty(cursor_row, cursor_column);
    }
}

static void clear_cells(void)
{
    unsigned char row;
    unsigned char column;

    for (row = 0; row < UDEKS_ROOT_CONSOLE_ROWS; ++row) {
        for (column = 0; column < UDEKS_ROOT_CONSOLE_COLUMNS; ++column) {
            cells[row][column] = ' ';
        }
        cells[row][UDEKS_ROOT_CONSOLE_COLUMNS] = 0;
    }
}

static void scroll_up(void)
{
    unsigned char row;
    unsigned char column;

    for (row = 1; row < UDEKS_ROOT_CONSOLE_ROWS; ++row) {
        for (column = 0; column < UDEKS_ROOT_CONSOLE_ROW_STRIDE; ++column) {
            cells[row - 1u][column] = cells[row][column];
        }
    }
    for (column = 0; column < UDEKS_ROOT_CONSOLE_COLUMNS; ++column) {
        cells[UDEKS_ROOT_CONSOLE_ROWS - 1u][column] = ' ';
    }
    cells[UDEKS_ROOT_CONSOLE_ROWS - 1u][UDEKS_ROOT_CONSOLE_COLUMNS] = 0;
    mark_all_dirty();
}

static void advance_line(void)
{
    cursor_column = 0;
    if (cursor_row + 1u < UDEKS_ROOT_CONSOLE_ROWS) {
        ++cursor_row;
    } else {
        scroll_up();
    }
}

static void write_printable(unsigned char character)
{
    mark_cursor_dirty();
    if (cells[cursor_row][cursor_column] != character) {
        cells[cursor_row][cursor_column] = character;
        mark_cell_dirty(cursor_row, cursor_column);
    }
    ++cursor_column;
    if (cursor_column == UDEKS_ROOT_CONSOLE_COLUMNS) {
        advance_line();
    }
    mark_cursor_dirty();
}

void udeks_root_console_reset(void)
{
    clear_cells();
    cursor_column = 0;
    cursor_row = 0;
    cursor_visible = 0;
    mark_all_dirty();
}

void udeks_root_console_clear(void)
{
    mark_cursor_dirty();
    clear_cells();
    cursor_column = 0;
    cursor_row = 0;
    mark_all_dirty();
}

unsigned char udeks_root_console_write_at(
    unsigned char column, unsigned char row, const unsigned char *text)
{
    if (column >= UDEKS_ROOT_CONSOLE_COLUMNS ||
        row >= UDEKS_ROOT_CONSOLE_ROWS) {
        return UDEKS_ROOT_CONSOLE_BOUNDS;
    }
    while (*text != 0 && column < UDEKS_ROOT_CONSOLE_COLUMNS) {
        if (cells[row][column] != *text) {
            cells[row][column] = *text;
            mark_cell_dirty(row, column);
        }
        ++column;
        ++text;
    }
    return UDEKS_ROOT_CONSOLE_OK;
}

unsigned char udeks_root_console_put(
    unsigned char column, unsigned char row, unsigned char character)
{
    if (column >= UDEKS_ROOT_CONSOLE_COLUMNS ||
        row >= UDEKS_ROOT_CONSOLE_ROWS) {
        return UDEKS_ROOT_CONSOLE_BOUNDS;
    }
    if (cells[row][column] != character) {
        cells[row][column] = character;
        mark_cell_dirty(row, column);
    }
    return UDEKS_ROOT_CONSOLE_OK;
}

void udeks_root_console_write(unsigned char character)
{
    unsigned char spaces;

    if (character == '\r') {
        mark_cursor_dirty();
        cursor_column = 0;
        mark_cursor_dirty();
    } else if (character == '\n') {
        mark_cursor_dirty();
        advance_line();
        mark_cursor_dirty();
    } else if (character == '\b') {
        if (cursor_column != 0) {
            mark_cursor_dirty();
            --cursor_column;
            mark_cursor_dirty();
        }
    } else if (character == '\t') {
        spaces = (unsigned char)(
            UDEKS_ROOT_CONSOLE_TAB_WIDTH -
            (cursor_column & (UDEKS_ROOT_CONSOLE_TAB_WIDTH - 1u)));
        while (spaces != 0) {
            write_printable(' ');
            --spaces;
        }
    } else if (character == '\f') {
        udeks_root_console_clear();
    } else if (character >= ' ') {
        write_printable(character);
    }
}

void udeks_root_console_write_string(const unsigned char *text)
{
    while (*text != 0) {
        udeks_root_console_write(*text);
        ++text;
    }
}

unsigned char udeks_root_console_set_cursor(
    unsigned char column, unsigned char row, unsigned char visible)
{
    if (column >= UDEKS_ROOT_CONSOLE_COLUMNS ||
        row >= UDEKS_ROOT_CONSOLE_ROWS) {
        return UDEKS_ROOT_CONSOLE_BOUNDS;
    }
    mark_cursor_dirty();
    cursor_column = column;
    cursor_row = row;
    cursor_visible = visible != 0;
    mark_cursor_dirty();
    return UDEKS_ROOT_CONSOLE_OK;
}

const unsigned char *udeks_root_console_row(unsigned char row)
{
    if (row >= UDEKS_ROOT_CONSOLE_ROWS) {
        row = 0;
    }
    return cells[row];
}

unsigned char udeks_root_console_row_dirty(unsigned char row)
{
    if (row >= UDEKS_ROOT_CONSOLE_ROWS) {
        return 0;
    }
    return dirty_rows[row];
}

unsigned char udeks_root_console_dirty_span(
    unsigned char row, unsigned char *first, unsigned char *last)
{
    if (row >= UDEKS_ROOT_CONSOLE_ROWS || dirty_rows[row] == 0) {
        return 0;
    }
    *first = dirty_first[row];
    *last = dirty_last[row];
    return 1;
}

void udeks_root_console_mark_row_clean(unsigned char row)
{
    if (row < UDEKS_ROOT_CONSOLE_ROWS) {
        dirty_rows[row] = 0;
        dirty_first[row] = 0;
        dirty_last[row] = 0;
    }
}

void udeks_root_console_mark_all_clean(void)
{
    unsigned char row;

    for (row = 0; row < UDEKS_ROOT_CONSOLE_ROWS; ++row) {
        dirty_rows[row] = 0;
        dirty_first[row] = 0;
        dirty_last[row] = 0;
    }
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
