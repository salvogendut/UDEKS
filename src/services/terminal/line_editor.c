/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/keyboard.h"
#include "udeks/line_editor.h"

static unsigned char edit_text[UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char submitted_text[UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char edit_length;
static unsigned char edit_cursor;
static unsigned char submitted_length;
static unsigned char submitted_ready;

void udeks_line_editor_initialize(void)
{
    submitted_length = 0;
    submitted_ready = 0;
    submitted_text[0] = 0;
    udeks_line_editor_reset();
}

void udeks_line_editor_reset(void)
{
    edit_length = 0;
    edit_cursor = 0;
    edit_text[0] = 0;
}

static unsigned char move_left(void)
{
    if (edit_cursor == 0) {
        return UDEKS_LINE_EDITOR_ACTION_NONE;
    }
    --edit_cursor;
    return UDEKS_LINE_EDITOR_ACTION_CURSOR;
}

static unsigned char move_right(void)
{
    if (edit_cursor == edit_length) {
        return UDEKS_LINE_EDITOR_ACTION_NONE;
    }
    ++edit_cursor;
    return UDEKS_LINE_EDITOR_ACTION_CURSOR;
}

static unsigned char erase_left(void)
{
    unsigned char index;

    if (edit_cursor == 0) {
        return UDEKS_LINE_EDITOR_ACTION_NONE;
    }
    --edit_cursor;
    --edit_length;
    for (index = edit_cursor; index < edit_length; ++index) {
        edit_text[index] = edit_text[index + 1u];
    }
    edit_text[edit_length] = 0;
    return UDEKS_LINE_EDITOR_ACTION_TEXT;
}

static unsigned char insert_character(unsigned char character)
{
    unsigned char index;

    if (edit_length == UDEKS_LINE_EDITOR_CAPACITY) {
        return UDEKS_LINE_EDITOR_ACTION_NONE;
    }
    index = edit_length;
    while (index > edit_cursor) {
        edit_text[index] = edit_text[index - 1u];
        --index;
    }
    edit_text[edit_cursor] = character;
    ++edit_cursor;
    ++edit_length;
    edit_text[edit_length] = 0;
    return UDEKS_LINE_EDITOR_ACTION_TEXT;
}

unsigned char udeks_line_editor_handle(
    unsigned char scan_code, unsigned char character,
    unsigned char modifiers)
{
    if (character == '\n') {
        return UDEKS_LINE_EDITOR_ACTION_SUBMIT;
    }
    if (character == '\b') {
        return erase_left();
    }
    if (scan_code == UDEKS_KEY_SCAN_CURSOR_LEFT ||
        (scan_code == UDEKS_KEY_SCAN_CURSOR_RIGHT &&
         (modifiers & UDEKS_KEY_MOD_SHIFT) != 0)) {
        return move_left();
    }
    if (scan_code == UDEKS_KEY_SCAN_CURSOR_RIGHT_EXT ||
        (scan_code == UDEKS_KEY_SCAN_CURSOR_RIGHT &&
         (modifiers & UDEKS_KEY_MOD_SHIFT) == 0)) {
        return move_right();
    }
    if (scan_code == UDEKS_KEY_SCAN_HOME) {
        if (edit_cursor == 0) {
            return UDEKS_LINE_EDITOR_ACTION_NONE;
        }
        edit_cursor = 0;
        return UDEKS_LINE_EDITOR_ACTION_CURSOR;
    }
    if (character >= ' ' && character <= '~') {
        return insert_character(character);
    }
    return UDEKS_LINE_EDITOR_ACTION_NONE;
}

unsigned char udeks_line_editor_submit(void)
{
    unsigned char index;
    unsigned char overwritten;

    overwritten = submitted_ready;
    for (index = 0; index <= edit_length; ++index) {
        submitted_text[index] = edit_text[index];
    }
    submitted_length = edit_length;
    submitted_ready = 1;
    udeks_line_editor_reset();
    return overwritten;
}

unsigned char udeks_line_editor_get_line(
    unsigned char *text, unsigned char capacity)
{
    unsigned char index;

    if (submitted_ready == 0) {
        return UDEKS_LINE_EDITOR_EMPTY;
    }
    if (capacity <= submitted_length) {
        return UDEKS_LINE_EDITOR_TOO_SMALL;
    }
    for (index = 0; index <= submitted_length; ++index) {
        text[index] = submitted_text[index];
    }
    submitted_ready = 0;
    return UDEKS_LINE_EDITOR_OK;
}

const unsigned char *udeks_line_editor_text(void)
{
    return edit_text;
}

unsigned char udeks_line_editor_length(void)
{
    return edit_length;
}

unsigned char udeks_line_editor_cursor(void)
{
    return edit_cursor;
}

unsigned char udeks_line_editor_submission_ready(void)
{
    return submitted_ready;
}

unsigned char udeks_line_editor_submitted_length(void)
{
    return submitted_length;
}
