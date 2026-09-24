/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_LINE_EDITOR_H
#define UDEKS_LINE_EDITOR_H

#define UDEKS_LINE_EDITOR_CAPACITY       54u
#define UDEKS_LINE_EDITOR_HISTORY_CAPACITY 6u

#define UDEKS_LINE_EDITOR_ACTION_NONE    0u
#define UDEKS_LINE_EDITOR_ACTION_CURSOR  1u
#define UDEKS_LINE_EDITOR_ACTION_TEXT    2u
#define UDEKS_LINE_EDITOR_ACTION_SUBMIT  3u
#define UDEKS_LINE_EDITOR_ACTION_REPLACE 4u

#define UDEKS_LINE_EDITOR_OK             0u
#define UDEKS_LINE_EDITOR_EMPTY          1u
#define UDEKS_LINE_EDITOR_TOO_SMALL      2u

void udeks_line_editor_initialize(void);
void udeks_line_editor_reset(void);
unsigned char udeks_line_editor_handle(
    unsigned char scan_code, unsigned char character,
    unsigned char modifiers);
unsigned char udeks_line_editor_submit(void);
unsigned char udeks_line_editor_get_line(
    unsigned char *text, unsigned char capacity);
const unsigned char *udeks_line_editor_text(void);
unsigned char udeks_line_editor_length(void);
unsigned char udeks_line_editor_cursor(void);
unsigned char udeks_line_editor_submission_ready(void);
unsigned char udeks_line_editor_submitted_length(void);
unsigned char udeks_line_editor_history_count(void);
unsigned char udeks_line_editor_history_position(void);

#endif
