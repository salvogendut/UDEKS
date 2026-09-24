/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_KEYBOARD_H
#define UDEKS_KEYBOARD_H

#define UDEKS_KEYBOARD_STATUS_BASE       0xF120u
#define UDEKS_KEYBOARD_STATUS_SIZE       48u
#define UDEKS_KEYBOARD_MATRIX_LINES      11u
#define UDEKS_KEYBOARD_QUEUE_CAPACITY    16u

#define UDEKS_KEYBOARD_STATE_STARTING    1u
#define UDEKS_KEYBOARD_STATE_READY       2u
#define UDEKS_KEYBOARD_STATE_ERROR       0x80u

#define UDEKS_KEY_EVENT_PRESS            1u
#define UDEKS_KEY_EVENT_RELEASE          2u

#define UDEKS_KEY_MOD_SHIFT              0x01u
#define UDEKS_KEY_MOD_CONTROL            0x02u
#define UDEKS_KEY_MOD_COMMODORE          0x04u
#define UDEKS_KEY_MOD_ALT                0x08u
#define UDEKS_KEY_MOD_CAPS               0x10u

#define UDEKS_KEY_SCAN_DELETE            0u
#define UDEKS_KEY_SCAN_RETURN            1u
#define UDEKS_KEY_SCAN_CURSOR_RIGHT      2u
#define UDEKS_KEY_SCAN_F7                 3u
#define UDEKS_KEY_SCAN_F1                 4u
#define UDEKS_KEY_SCAN_F3                 5u
#define UDEKS_KEY_SCAN_F5                 6u
#define UDEKS_KEY_SCAN_CURSOR_DOWN        7u
#define UDEKS_KEY_SCAN_LEFT_SHIFT         15u
#define UDEKS_KEY_SCAN_RIGHT_SHIFT        52u
#define UDEKS_KEY_SCAN_CONTROL            58u
#define UDEKS_KEY_SCAN_COMMODORE          61u
#define UDEKS_KEY_SCAN_HELP               64u
#define UDEKS_KEY_SCAN_TAB                67u
#define UDEKS_KEY_SCAN_ESCAPE             72u
#define UDEKS_KEY_SCAN_LINE_FEED          75u
#define UDEKS_KEY_SCAN_KEYPAD_ENTER       76u
#define UDEKS_KEY_SCAN_ALT                80u
#define UDEKS_KEY_SCAN_CURSOR_UP          83u
#define UDEKS_KEY_SCAN_CURSOR_DOWN_EXT    84u
#define UDEKS_KEY_SCAN_CURSOR_LEFT        85u
#define UDEKS_KEY_SCAN_CURSOR_RIGHT_EXT   86u
#define UDEKS_KEY_SCAN_NO_SCROLL          87u

#define UDEKS_KEYBOARD_OK                 0u
#define UDEKS_KEYBOARD_EMPTY              1u

struct udeks_key_event {
    unsigned char type;
    unsigned char scan_code;
    unsigned char character;
    unsigned char modifiers;
};

extern unsigned char udeks_keyboard_matrix[UDEKS_KEYBOARD_MATRIX_LINES];
extern unsigned char udeks_keyboard_caps;
extern unsigned char udeks_keyboard_display_80;

void udeks_keyboard_scan(void);
unsigned char udeks_keyboard_start(void);
unsigned char udeks_keyboard_poll(void);
unsigned char udeks_keyboard_event_get(struct udeks_key_event *event);
unsigned char udeks_keyboard_normalize(
    unsigned char scan_code, unsigned char modifiers);

#endif
