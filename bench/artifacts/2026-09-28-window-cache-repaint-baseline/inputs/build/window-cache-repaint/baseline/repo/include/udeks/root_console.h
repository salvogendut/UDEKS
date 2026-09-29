/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_ROOT_CONSOLE_H
#define UDEKS_ROOT_CONSOLE_H

#define UDEKS_ROOT_CONSOLE_COLUMNS     64u
#define UDEKS_ROOT_CONSOLE_ROWS        21u
#define UDEKS_ROOT_CONSOLE_ROW_STRIDE  65u
#define UDEKS_ROOT_CONSOLE_TAB_WIDTH   8u

#define UDEKS_ROOT_CONSOLE_OK          0u
#define UDEKS_ROOT_CONSOLE_BOUNDS      1u

void udeks_root_console_reset(void);
void udeks_root_console_clear(void);
unsigned char udeks_root_console_write_at(
    unsigned char column, unsigned char row, const unsigned char *text);
unsigned char udeks_root_console_put(
    unsigned char column, unsigned char row, unsigned char character);
void udeks_root_console_write(unsigned char character);
void udeks_root_console_write_string(const unsigned char *text);
unsigned char udeks_root_console_set_cursor(
    unsigned char column, unsigned char row, unsigned char visible);
const unsigned char *udeks_root_console_row(unsigned char row);
unsigned char udeks_root_console_row_dirty(unsigned char row);
unsigned char udeks_root_console_dirty_span(
    unsigned char row, unsigned char *first, unsigned char *last);
void udeks_root_console_mark_row_clean(unsigned char row);
void udeks_root_console_mark_all_clean(void);
unsigned char udeks_root_console_cursor_column(void);
unsigned char udeks_root_console_cursor_row(void);
unsigned char udeks_root_console_cursor_visible(void);

#endif
