/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/keyboard.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_KEYBOARD_STATUS_BASE + (offset)))

#define STATUS_FLAGS             17u
#define STATUS_POLL_LO           18u
#define STATUS_POLL_HI           19u
#define STATUS_PRESS_LO          20u
#define STATUS_PRESS_HI          21u
#define STATUS_RELEASE_LO        22u
#define STATUS_RELEASE_HI        23u
#define STATUS_MATRIX            24u
#define STATUS_LAST_PRESS_SCAN   35u
#define STATUS_LAST_PRESS_CHAR   36u
#define STATUS_LAST_PRESS_MODS   37u

#define KEYBOARD_FLAG_STANDARD   0x01u
#define KEYBOARD_FLAG_EXTENDED   0x02u
#define KEYBOARD_FLAG_PRESERVED  0x04u
#define KEYBOARD_FLAG_QUEUED     0x08u

static const unsigned char normal_map[88] = {
    '\b', '\n', 0, 0, 0, 0, 0, 0,
    '3', 'w', 'a', '4', 'z', 's', 'e', 0,
    '5', 'r', 'd', '6', 'c', 'f', 't', 'x',
    '7', 'y', 'g', '8', 'b', 'h', 'u', 'v',
    '9', 'i', 'j', '0', 'm', 'k', 'o', 'n',
    '+', 'p', 'l', '-', '.', ':', '@', ',',
    0, '*', ';', 0, 0, '=', 0, '/',
    '1', 0, 0, '2', ' ', 0, 'q', 0,
    0, '8', '5', '\t', '2', '4', '7', '1',
    0x1B, '+', '-', '\n', '\n', '6', '9', '3',
    0, '0', '.', 0, 0, 0, 0, 0
};

static const unsigned char shifted_map[88] = {
    '\b', '\n', 0, 0, 0, 0, 0, 0,
    '#', 'W', 'A', '$', 'Z', 'S', 'E', 0,
    '%', 'R', 'D', '&', 'C', 'F', 'T', 'X',
    '\'', 'Y', 'G', '(', 'B', 'H', 'U', 'V',
    ')', 'I', 'J', '0', 'M', 'K', 'O', 'N',
    '+', 'P', 'L', '-', '>', '[', '@', '<',
    0, '*', ']', 0, 0, '=', 0, '?',
    '!', 0, 0, '"', ' ', 0, 'Q', 0,
    0, '8', '5', '\t', '2', '4', '7', '1',
    0x1B, '+', '-', '\n', '\n', '6', '9', '3',
    0, '0', '.', 0, 0, 0, 0, 0
};

static unsigned char previous_matrix[UDEKS_KEYBOARD_MATRIX_LINES];
static struct udeks_key_event event_queue[UDEKS_KEYBOARD_QUEUE_CAPACITY];
static unsigned char queue_head;
static unsigned char queue_tail;
static unsigned char queue_count;
static unsigned char scan_line;
static unsigned char sense_bit;
static unsigned char scan_code;
static unsigned char modifiers;

static unsigned char key_pressed(unsigned char code)
{
    return (unsigned char)(
        udeks_keyboard_matrix[code >> 3] & (1u << (code & 7u)));
}

static unsigned char current_modifiers(void)
{
    unsigned char result;

    result = 0;
    if (key_pressed(UDEKS_KEY_SCAN_LEFT_SHIFT) != 0 ||
        key_pressed(UDEKS_KEY_SCAN_RIGHT_SHIFT) != 0) {
        result |= UDEKS_KEY_MOD_SHIFT;
    }
    if (key_pressed(UDEKS_KEY_SCAN_CONTROL) != 0) {
        result |= UDEKS_KEY_MOD_CONTROL;
    }
    if (key_pressed(UDEKS_KEY_SCAN_COMMODORE) != 0) {
        result |= UDEKS_KEY_MOD_COMMODORE;
    }
    if (key_pressed(UDEKS_KEY_SCAN_ALT) != 0) {
        result |= UDEKS_KEY_MOD_ALT;
    }
    if (udeks_keyboard_caps != 0) {
        result |= UDEKS_KEY_MOD_CAPS;
    }
    return result;
}

unsigned char udeks_keyboard_normalize(
    unsigned char code, unsigned char event_modifiers)
{
    unsigned char character;
    unsigned char shifted;

    if (code >= 88u) {
        return 0;
    }
    shifted = (unsigned char)(event_modifiers & UDEKS_KEY_MOD_SHIFT);
    character = normal_map[code];
    if (character >= 'a' && character <= 'z') {
        if ((event_modifiers & UDEKS_KEY_MOD_CAPS) != 0) {
            shifted ^= UDEKS_KEY_MOD_SHIFT;
        }
        if (shifted != 0) {
            character = shifted_map[code];
        }
        if ((event_modifiers & UDEKS_KEY_MOD_CONTROL) != 0) {
            character = (unsigned char)(character & 0x1Fu);
        }
    } else if (shifted != 0) {
        character = shifted_map[code];
    }
    return character;
}

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static void enqueue_event(unsigned char type, unsigned char code)
{
    struct udeks_key_event *event;

    if (queue_count == UDEKS_KEYBOARD_QUEUE_CAPACITY) {
        ++STATUS_BYTE(10);
        return;
    }
    event = &event_queue[queue_head];
    event->type = type;
    event->scan_code = code;
    event->character = udeks_keyboard_normalize(code, modifiers);
    event->modifiers = modifiers;
    ++queue_head;
    if (queue_head == UDEKS_KEYBOARD_QUEUE_CAPACITY) {
        queue_head = 0;
    }
    ++queue_count;
    STATUS_BYTE(9) = queue_count;
    STATUS_BYTE(11) = type;
    STATUS_BYTE(12) = code;
    STATUS_BYTE(13) = event->character;
    STATUS_BYTE(14) = modifiers;
    if (type == UDEKS_KEY_EVENT_PRESS) {
        STATUS_BYTE(STATUS_LAST_PRESS_SCAN) = code;
        STATUS_BYTE(STATUS_LAST_PRESS_CHAR) = event->character;
        STATUS_BYTE(STATUS_LAST_PRESS_MODS) = modifiers;
        increment_counter(STATUS_PRESS_LO);
    } else {
        increment_counter(STATUS_RELEASE_LO);
    }
}

static void publish_switches_and_matrix(void)
{
    STATUS_BYTE(15) = udeks_keyboard_caps;
    STATUS_BYTE(16) = udeks_keyboard_display_80;
    for (scan_line = 0; scan_line < UDEKS_KEYBOARD_MATRIX_LINES; ++scan_line) {
        STATUS_BYTE(STATUS_MATRIX + scan_line) =
            udeks_keyboard_matrix[scan_line];
    }
}

unsigned char udeks_keyboard_start(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_KEYBOARD_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'K';
    STATUS_BYTE(1) = 'E';
    STATUS_BYTE(2) = 'Y';
    STATUS_BYTE(3) = 'B';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_KEYBOARD_STATE_STARTING;
    STATUS_BYTE(7) = UDEKS_KEYBOARD_MATRIX_LINES;
    STATUS_BYTE(8) = UDEKS_KEYBOARD_QUEUE_CAPACITY;
    STATUS_BYTE(STATUS_FLAGS) =
        KEYBOARD_FLAG_STANDARD | KEYBOARD_FLAG_EXTENDED |
        KEYBOARD_FLAG_PRESERVED | KEYBOARD_FLAG_QUEUED;
    queue_head = 0;
    queue_tail = 0;
    queue_count = 0;
    udeks_keyboard_scan();
    for (scan_line = 0; scan_line < UDEKS_KEYBOARD_MATRIX_LINES; ++scan_line) {
        previous_matrix[scan_line] = udeks_keyboard_matrix[scan_line];
    }
    publish_switches_and_matrix();
    STATUS_BYTE(5) = UDEKS_KEYBOARD_STATE_READY;
    return UDEKS_KEYBOARD_OK;
}

unsigned char udeks_keyboard_poll(void)
{
    unsigned char changed;
    unsigned char mask;

    udeks_keyboard_scan();
    modifiers = current_modifiers();
    for (scan_line = 0; scan_line < UDEKS_KEYBOARD_MATRIX_LINES; ++scan_line) {
        changed = (unsigned char)(
            udeks_keyboard_matrix[scan_line] ^ previous_matrix[scan_line]);
        mask = 1;
        for (sense_bit = 0; sense_bit < 8u; ++sense_bit) {
            if ((changed & mask) != 0) {
                scan_code = (unsigned char)(scan_line * 8u + sense_bit);
                enqueue_event(
                    (udeks_keyboard_matrix[scan_line] & mask) != 0 ?
                        UDEKS_KEY_EVENT_PRESS : UDEKS_KEY_EVENT_RELEASE,
                    scan_code);
            }
            mask <<= 1;
        }
        previous_matrix[scan_line] = udeks_keyboard_matrix[scan_line];
    }
    publish_switches_and_matrix();
    increment_counter(STATUS_POLL_LO);
    return UDEKS_KEYBOARD_OK;
}

unsigned char udeks_keyboard_event_get(struct udeks_key_event *event)
{
    if (queue_count == 0) {
        return UDEKS_KEYBOARD_EMPTY;
    }
    *event = event_queue[queue_tail];
    ++queue_tail;
    if (queue_tail == UDEKS_KEYBOARD_QUEUE_CAPACITY) {
        queue_tail = 0;
    }
    --queue_count;
    STATUS_BYTE(9) = queue_count;
    return UDEKS_KEYBOARD_OK;
}
