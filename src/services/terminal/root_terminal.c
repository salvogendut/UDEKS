/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/console.h"
#include "udeks/keyboard.h"
#include "udeks/line_editor.h"
#include "udeks/root_console.h"
#include "udeks/root_terminal.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_ROOT_TERMINAL_STATUS_BASE + (offset)))

#define STATUS_POLLS_LO             12u
#define STATUS_PRESSES_LO           14u
#define STATUS_EDITS_LO             16u
#define STATUS_SUBMISSIONS_LO       18u
#define STATUS_LAST_LENGTH          20u
#define STATUS_LAST_SUM_LO          21u
#define STATUS_LAST_SUM_HI          22u
#define STATUS_OVERWRITES           23u
#define STATUS_REFRESHES_LO         24u

#define INPUT_FIELD_WIDTH           55u

static const unsigned char prompt[] = "UDEKS:~> ";
static unsigned char input_row;
static unsigned char input_column;
static unsigned char pending_refresh;
static struct udeks_key_event event;

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static unsigned char terminal_fail(unsigned char code)
{
    STATUS_BYTE(6) = code;
    STATUS_BYTE(5) = (unsigned char)(UDEKS_ROOT_TERMINAL_ERROR | code);
    return code;
}

static void publish_editor_state(void)
{
    STATUS_BYTE(8) = udeks_line_editor_length();
    STATUS_BYTE(9) = udeks_line_editor_cursor();
    STATUS_BYTE(10) = pending_refresh;
    STATUS_BYTE(11) = 0;
}

static unsigned char move_display_cursor(void)
{
    if (udeks_root_console_set_cursor(
            (unsigned char)(input_column + udeks_line_editor_cursor()),
            input_row, 1) != UDEKS_ROOT_CONSOLE_OK) {
        return UDEKS_ROOT_TERMINAL_RENDER;
    }
    pending_refresh = 1;
    return UDEKS_ROOT_TERMINAL_OK;
}

static unsigned char render_editor_range(
    unsigned char first, unsigned char last)
{
    const unsigned char *text;
    unsigned char index;

    text = udeks_line_editor_text();
    for (index = first; index <= last; ++index) {
        if (udeks_root_console_put(
                (unsigned char)(input_column + index), input_row,
                index < udeks_line_editor_length() ? text[index] : ' ') !=
                UDEKS_ROOT_CONSOLE_OK) {
            return UDEKS_ROOT_TERMINAL_RENDER;
        }
    }
    return move_display_cursor();
}

static void publish_submission(void)
{
    const unsigned char *text;
    unsigned int checksum;
    unsigned char index;

    text = udeks_line_editor_text();
    checksum = 0;
    for (index = 0; index < udeks_line_editor_length(); ++index) {
        checksum += text[index];
    }
    STATUS_BYTE(STATUS_LAST_LENGTH) = udeks_line_editor_length();
    STATUS_BYTE(STATUS_LAST_SUM_LO) = (unsigned char)checksum;
    STATUS_BYTE(STATUS_LAST_SUM_HI) = (unsigned char)(checksum >> 8);
}

static unsigned char submit_line(void)
{
    publish_submission();
    if (udeks_line_editor_submit() != 0) {
        ++STATUS_BYTE(STATUS_OVERWRITES);
    }
    increment_counter(STATUS_SUBMISSIONS_LO);
    udeks_root_console_write('\n');
    udeks_root_console_write_string(prompt);
    input_column = udeks_root_console_cursor_column();
    input_row = udeks_root_console_cursor_row();
    if ((unsigned int)input_column + INPUT_FIELD_WIDTH >
            UDEKS_ROOT_CONSOLE_COLUMNS) {
        return terminal_fail(UDEKS_ROOT_TERMINAL_RENDER);
    }
    pending_refresh = 1;
    return UDEKS_ROOT_TERMINAL_OK;
}

static unsigned char refresh_display(void)
{
    unsigned char result;

    if (pending_refresh == 0) {
        return UDEKS_ROOT_TERMINAL_OK;
    }
    result = udeks_console_refresh_root();
    if (result != UDEKS_CONSOLE_OK) {
        return UDEKS_ROOT_TERMINAL_RENDER;
    }
    pending_refresh = 0;
    increment_counter(STATUS_REFRESHES_LO);
    return UDEKS_ROOT_TERMINAL_OK;
}

unsigned char udeks_root_terminal_start(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_ROOT_TERMINAL_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'R';
    STATUS_BYTE(1) = 'C';
    STATUS_BYTE(2) = 'L';
    STATUS_BYTE(3) = 'I';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_ROOT_TERMINAL_STARTING;
    STATUS_BYTE(7) = UDEKS_LINE_EDITOR_CAPACITY;
    if (*(volatile unsigned char *)(UDEKS_KEYBOARD_STATUS_BASE + 5u) !=
            UDEKS_KEYBOARD_STATE_READY ||
        *(volatile unsigned char *)(UDEKS_CONSOLE_STATUS_BASE + 5u) !=
            UDEKS_CONSOLE_STATE_READY) {
        return terminal_fail(UDEKS_ROOT_TERMINAL_DEPENDENCY);
    }
    udeks_line_editor_initialize();
    input_column = udeks_root_console_cursor_column();
    input_row = udeks_root_console_cursor_row();
    pending_refresh = 0;
    publish_editor_state();
    STATUS_BYTE(5) = UDEKS_ROOT_TERMINAL_READY;
    return UDEKS_ROOT_TERMINAL_OK;
}

unsigned char udeks_root_terminal_poll(void)
{
    unsigned char action;
    unsigned char result;
    unsigned char old_cursor;
    unsigned char old_length;
    unsigned char first;
    unsigned char last;

    while (udeks_keyboard_event_get(&event) == UDEKS_KEYBOARD_OK) {
        if (event.type != UDEKS_KEY_EVENT_PRESS) {
            continue;
        }
        increment_counter(STATUS_PRESSES_LO);
        old_cursor = udeks_line_editor_cursor();
        old_length = udeks_line_editor_length();
        action = udeks_line_editor_handle(
            event.scan_code, event.character, event.modifiers);
        if (action == UDEKS_LINE_EDITOR_ACTION_SUBMIT) {
            result = submit_line();
            if (result != UDEKS_ROOT_TERMINAL_OK) {
                return terminal_fail(result);
            }
        } else if (action != UDEKS_LINE_EDITOR_ACTION_NONE) {
            increment_counter(STATUS_EDITS_LO);
            if (action == UDEKS_LINE_EDITOR_ACTION_CURSOR) {
                result = move_display_cursor();
            } else {
                first = old_cursor < udeks_line_editor_cursor() ?
                    old_cursor : udeks_line_editor_cursor();
                last = old_length > udeks_line_editor_length() ?
                    old_length : udeks_line_editor_length();
                --last;
                result = render_editor_range(first, last);
            }
            if (result != UDEKS_ROOT_TERMINAL_OK) {
                return terminal_fail(result);
            }
        }
    }
    result = refresh_display();
    if (result != UDEKS_ROOT_TERMINAL_OK) {
        return terminal_fail(result);
    }
    publish_editor_state();
    increment_counter(STATUS_POLLS_LO);
    return UDEKS_ROOT_TERMINAL_OK;
}
