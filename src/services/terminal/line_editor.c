/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/keyboard.h"
#include "udeks/line_editor.h"

static unsigned char edit_text[UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char submitted_text[UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char history_text[UDEKS_LINE_EDITOR_HISTORY_CAPACITY]
    [UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char history_length[UDEKS_LINE_EDITOR_HISTORY_CAPACITY];
static unsigned char draft_text[UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char edit_length;
static unsigned char edit_cursor;
static unsigned char submitted_length;
static unsigned char submitted_ready;
static unsigned char history_count;
static unsigned char history_position;
static unsigned char draft_length;

void udeks_line_editor_initialize(void)
{
    submitted_length = 0;
    submitted_ready = 0;
    submitted_text[0] = 0;
    history_count = 0;
    history_position = 0;
    draft_length = 0;
    draft_text[0] = 0;
    udeks_line_editor_reset();
}

void udeks_line_editor_reset(void)
{
    edit_length = 0;
    edit_cursor = 0;
    edit_text[0] = 0;
    history_position = history_count;
}

static void copy_line(
    unsigned char *destination, const unsigned char *source,
    unsigned char length)
{
    unsigned char index;

    for (index = 0; index <= length; ++index) {
        destination[index] = source[index];
    }
}

static void load_line(const unsigned char *source, unsigned char length)
{
    copy_line(edit_text, source, length);
    edit_length = length;
    edit_cursor = length;
}

static void leave_history(void)
{
    history_position = history_count;
}

static unsigned char lines_equal(
    const unsigned char *left, const unsigned char *right,
    unsigned char length)
{
    unsigned char index;

    for (index = 0; index < length; ++index) {
        if (left[index] != right[index]) {
            return 0;
        }
    }
    return 1;
}

static void remember_line(void)
{
    unsigned char entry;

    if (edit_length == 0) {
        return;
    }
    if (history_count != 0 &&
        history_length[history_count - 1u] == edit_length &&
        lines_equal(history_text[history_count - 1u], edit_text, edit_length)) {
        return;
    }
    if (history_count == UDEKS_LINE_EDITOR_HISTORY_CAPACITY) {
        for (entry = 0;
             entry + 1u < UDEKS_LINE_EDITOR_HISTORY_CAPACITY;
             ++entry) {
            history_length[entry] = history_length[entry + 1u];
            copy_line(
                history_text[entry], history_text[entry + 1u],
                history_length[entry]);
        }
        --history_count;
    }
    history_length[history_count] = edit_length;
    copy_line(history_text[history_count], edit_text, edit_length);
    ++history_count;
}

static unsigned char history_previous(void)
{
    if (history_count == 0 || history_position == 0) {
        return UDEKS_LINE_EDITOR_ACTION_NONE;
    }
    if (history_position == history_count) {
        draft_length = edit_length;
        copy_line(draft_text, edit_text, edit_length);
    }
    --history_position;
    load_line(
        history_text[history_position], history_length[history_position]);
    return UDEKS_LINE_EDITOR_ACTION_REPLACE;
}

static unsigned char history_next(void)
{
    if (history_position == history_count) {
        return UDEKS_LINE_EDITOR_ACTION_NONE;
    }
    ++history_position;
    if (history_position == history_count) {
        load_line(draft_text, draft_length);
    } else {
        load_line(
            history_text[history_position], history_length[history_position]);
    }
    return UDEKS_LINE_EDITOR_ACTION_REPLACE;
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
    leave_history();
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
    leave_history();
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
    if (scan_code == UDEKS_KEY_SCAN_CURSOR_UP ||
        (scan_code == UDEKS_KEY_SCAN_CURSOR_DOWN &&
         (modifiers & UDEKS_KEY_MOD_SHIFT) != 0)) {
        return history_previous();
    }
    if (scan_code == UDEKS_KEY_SCAN_CURSOR_DOWN_EXT ||
        (scan_code == UDEKS_KEY_SCAN_CURSOR_DOWN &&
         (modifiers & UDEKS_KEY_MOD_SHIFT) == 0)) {
        return history_next();
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
    remember_line();
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

unsigned char udeks_line_editor_history_count(void)
{
    return history_count;
}

unsigned char udeks_line_editor_history_position(void)
{
    return history_position == history_count ? 0xFFu : history_position;
}
