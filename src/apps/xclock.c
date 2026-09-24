/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/pointer.h"
#include "udeks/time.h"
#include "udeks/vic_graphics.h"
#include "udeks/xclock.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_XCLOCK_STATUS_BASE + (offset)))

#define WINDOW_WIDTH       144u
#define WINDOW_HEIGHT      154u
#define TITLE_HEIGHT       13u
#define POINTER_X_BIAS     12u
#define POINTER_Y_BIAS     40u
#define ACTION_BUTTONS     0x05u

static const signed char sin64[60] = {
      0,  7, 13, 20, 26, 32, 38, 43, 48, 52, 55, 58,
     61, 63, 64, 64, 64, 63, 61, 58, 55, 52, 48, 43,
     38, 32, 26, 20, 13,  7,  0, -7,-13,-20,-26,-32,
    -38,-43,-48,-52,-55,-58,-61,-63,-64,-64,-64,-63,
    -61,-58,-55,-52,-48,-43,-38,-32,-26,-20,-13, -7
};

static const signed char cos64[60] = {
     64, 64, 63, 61, 58, 55, 52, 48, 43, 38, 32, 26,
     20, 13,  7,  0, -7,-13,-20,-26,-32,-38,-43,-48,
    -52,-55,-58,-61,-63,-64,-64,-64,-63,-61,-58,-55,
    -52,-48,-43,-38,-32,-26,-20,-13, -7,  0,  7, 13,
     20, 26, 32, 38, 43, 48, 52, 55, 58, 61, 63, 64
};

static const unsigned char digit_glyphs[11][5] = {
    {7, 5, 5, 5, 7}, {2, 6, 2, 2, 7}, {7, 1, 7, 4, 7},
    {7, 1, 7, 1, 7}, {5, 5, 7, 1, 1}, {7, 4, 7, 1, 7},
    {7, 4, 7, 5, 7}, {7, 1, 1, 1, 1}, {7, 5, 7, 5, 7},
    {7, 5, 7, 1, 7}, {0, 2, 0, 2, 0}
};

static const unsigned char title_glyphs[6][5] = {
    {5, 5, 2, 5, 5}, {7, 4, 4, 4, 7}, {4, 4, 4, 4, 7},
    {7, 5, 5, 5, 7}, {7, 4, 4, 4, 7}, {5, 5, 6, 5, 5}
};

static unsigned char window_x;
static unsigned char window_y;
static unsigned char face_x;
static unsigned char face_y;
static unsigned char previous_hour;
static unsigned char previous_minute;
static unsigned char previous_second;
static unsigned char previous_buttons;
static unsigned char dragging;
static unsigned char drag_x;
static unsigned char drag_y;

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static void publish_geometry(void)
{
    STATUS_BYTE(8) = window_x;
    STATUS_BYTE(9) = window_y;
    STATUS_BYTE(10) = WINDOW_WIDTH;
    STATUS_BYTE(11) = WINDOW_HEIGHT;
    STATUS_BYTE(24) = dragging;
}

static int point_x(unsigned char position, unsigned char radius)
{
    signed char component;
    unsigned int magnitude;

    component = sin64[position];
    magnitude = (unsigned int)(component < 0 ? -component : component);
    magnitude = (unsigned int)(magnitude * radius / 64u);
    return component < 0 ?
        (int)(face_x - magnitude) : (int)(face_x + magnitude);
}

static int point_y(unsigned char position, unsigned char radius)
{
    signed char component;
    unsigned int magnitude;

    component = cos64[position];
    magnitude = (unsigned int)(component < 0 ? -component : component);
    magnitude = (unsigned int)(magnitude * radius / 64u);
    return component < 0 ?
        (int)(face_y + magnitude) : (int)(face_y - magnitude);
}

static void draw_glyph(
    int x, int y, const unsigned char *glyph, unsigned char color)
{
    unsigned char row;
    unsigned char column;

    for (row = 0; row < 5u; ++row) {
        for (column = 0; column < 3u; ++column) {
            if ((glyph[row] & (unsigned char)(4u >> column)) != 0) {
                udeks_vic_bitmap_pixel(x + column, y + row, color);
            }
        }
    }
}

static void draw_title(void)
{
    unsigned char index;

    for (index = 0; index < 6u; ++index) {
        draw_glyph(
            window_x + 4 + (int)index * 4, window_y + 4,
            title_glyphs[index], UDEKS_VIC_COLOR_BLACK);
    }
}

static void draw_two_digits(int x, int y, unsigned char value)
{
    draw_glyph(x, y, digit_glyphs[value / 10u], UDEKS_VIC_COLOR_BLACK);
    draw_glyph(x + 4, y, digit_glyphs[value % 10u], UDEKS_VIC_COLOR_BLACK);
}

static void draw_digital(
    unsigned char hour, unsigned char minute)
{
    int x;
    int y;

    x = window_x + (WINDOW_WIDTH - 19u) / 2u;
    y = window_y + WINDOW_HEIGHT - 11u;
    udeks_vic_bitmap_fill(
        x - 2, y - 2, 23, 9, UDEKS_VIC_COLOR_YELLOW);
    draw_two_digits(x, y, hour);
    draw_glyph(x + 8, y, digit_glyphs[10], UDEKS_VIC_COLOR_BLACK);
    draw_two_digits(x + 12, y, minute);
}

static void draw_hand(
    unsigned char position, unsigned char length, unsigned char color)
{
    udeks_vic_bitmap_line(
        face_x, face_y, point_x(position, length),
        point_y(position, length), color);
}

static unsigned char hour_position(
    unsigned char hour, unsigned char minute)
{
    return (unsigned char)(((hour % 12u) * 5u + minute / 12u) % 60u);
}

static void draw_hands(
    unsigned char hour, unsigned char minute, unsigned char color)
{
    draw_hand(hour_position(hour, minute), 25u, color);
    draw_hand(minute, 36u, color);
}

static void draw_face(void)
{
    unsigned char position;
    unsigned char next;

    for (position = 0; position < 60u; position += 2u) {
        next = (unsigned char)((position + 2u) % 60u);
        udeks_vic_bitmap_line(
            point_x(position, 48u), point_y(position, 48u),
            point_x(next, 48u), point_y(next, 48u),
            UDEKS_VIC_COLOR_BLACK);
    }
    for (position = 0; position < 60u; position += 5u) {
        udeks_vic_bitmap_line(
            point_x(position, 48u), point_y(position, 48u),
            point_x(position, 42u), point_y(position, 42u),
            UDEKS_VIC_COLOR_BLACK);
    }
}

static void draw_frame(void)
{
    int close_x;

    udeks_vic_bitmap_rectangle(
        window_x, window_y, WINDOW_WIDTH, WINDOW_HEIGHT,
        UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_rectangle(
        window_x + 2, window_y + 2, WINDOW_WIDTH - 4,
        WINDOW_HEIGHT - 4, UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_line(
        window_x + 2, window_y + TITLE_HEIGHT,
        window_x + WINDOW_WIDTH - 3, window_y + TITLE_HEIGHT,
        UDEKS_VIC_COLOR_BLACK);
    draw_title();
    close_x = window_x + WINDOW_WIDTH - 12;
    udeks_vic_bitmap_rectangle(close_x, window_y + 3, 8, 8,
        UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_line(close_x + 2, window_y + 5,
        close_x + 5, window_y + 8, UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_line(close_x + 5, window_y + 5,
        close_x + 2, window_y + 8, UDEKS_VIC_COLOR_BLACK);
}

static void full_repaint(void)
{
    unsigned char hour;
    unsigned char minute;
    unsigned char second;

    udeks_time_now(&hour, &minute, &second);
    face_x = (unsigned char)(window_x + WINDOW_WIDTH / 2u);
    face_y = (unsigned char)(window_y + 75u);
    udeks_vic_bitmap_clear(UDEKS_VIC_COLOR_YELLOW);
    draw_frame();
    draw_face();
    draw_hands(hour, minute, UDEKS_VIC_COLOR_BLACK);
    draw_digital(hour, minute);
    udeks_vic_bitmap_commit();
    previous_hour = hour;
    previous_minute = minute;
    previous_second = second;
    STATUS_BYTE(12) = hour;
    STATUS_BYTE(13) = minute;
    STATUS_BYTE(14) = second;
    increment_counter(16u);
}

static void update_time(void)
{
    unsigned char hour;
    unsigned char minute;
    unsigned char second;

    udeks_time_now(&hour, &minute, &second);
    if (hour == previous_hour && minute == previous_minute) {
        return;
    }
    draw_hands(
        previous_hour, previous_minute, UDEKS_VIC_COLOR_YELLOW);
    draw_hands(hour, minute, UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_pixel(face_x, face_y, UDEKS_VIC_COLOR_BLACK);
    draw_digital(hour, minute);
    udeks_vic_bitmap_commit();
    previous_hour = hour;
    previous_minute = minute;
    previous_second = second;
    STATUS_BYTE(12) = hour;
    STATUS_BYTE(13) = minute;
    STATUS_BYTE(14) = second;
    increment_counter(18u);
}

static unsigned char point_inside(
    unsigned int x, unsigned char y, unsigned char left,
    unsigned char top, unsigned char width, unsigned char height)
{
    return x >= left && x < (unsigned int)(left + width) &&
        y >= top && y < (unsigned char)(top + height);
}

static void update_window_input(void)
{
    unsigned int pointer_x;
    unsigned char pointer_y;
    unsigned char buttons;
    unsigned char pressed;
    unsigned char new_x;
    unsigned char new_y;

    pointer_x = udeks_pointer_x() - POINTER_X_BIAS;
    pointer_y = (unsigned char)(udeks_pointer_y() - POINTER_Y_BIAS);
    buttons = udeks_pointer_buttons();
    pressed = (unsigned char)(buttons & ACTION_BUTTONS);
    STATUS_BYTE(25) = (unsigned char)pointer_x;
    STATUS_BYTE(26) = (unsigned char)(pointer_x >> 8);
    STATUS_BYTE(27) = pointer_y;
    if (pressed != 0 && previous_buttons == 0) {
        if (point_inside(
                pointer_x, pointer_y,
                (unsigned char)(window_x + WINDOW_WIDTH - 12u),
                (unsigned char)(window_y + 3u), 8u, 8u)) {
            udeks_xclock_stop();
            previous_buttons = pressed;
            return;
        }
        if (point_inside(
                pointer_x, pointer_y, window_x, window_y,
                WINDOW_WIDTH, TITLE_HEIGHT)) {
            dragging = 1;
            drag_x = (unsigned char)(pointer_x - window_x);
            drag_y = (unsigned char)(pointer_y - window_y);
        }
    }
    if (pressed == 0) {
        dragging = 0;
    } else if (dragging != 0) {
        new_x = pointer_x > drag_x ?
            (unsigned char)(pointer_x - drag_x) : 0u;
        new_y = pointer_y > drag_y ?
            (unsigned char)(pointer_y - drag_y) : 0u;
        if (new_x > UDEKS_VIC_WIDTH - WINDOW_WIDTH) {
            new_x = UDEKS_VIC_WIDTH - WINDOW_WIDTH;
        }
        if (new_y > UDEKS_VIC_HEIGHT - WINDOW_HEIGHT) {
            new_y = UDEKS_VIC_HEIGHT - WINDOW_HEIGHT;
        }
        if (new_x != window_x || new_y != window_y) {
            window_x = new_x;
            window_y = new_y;
            full_repaint();
            increment_counter(20u);
        }
    }
    previous_buttons = pressed;
    publish_geometry();
}

unsigned char udeks_xclock_initialize(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_XCLOCK_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'X';
    STATUS_BYTE(1) = 'C';
    STATUS_BYTE(2) = 'L';
    STATUS_BYTE(3) = 'K';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_XCLOCK_READY;
    STATUS_BYTE(7) = 0x07u;
    window_x = 88u;
    window_y = 22u;
    previous_buttons = 0;
    dragging = 0;
    publish_geometry();
    return UDEKS_XCLOCK_OK;
}

unsigned char udeks_xclock_start(void)
{
    if (STATUS_BYTE(5) == UDEKS_XCLOCK_RUNNING) {
        return UDEKS_XCLOCK_ALREADY_RUNNING;
    }
    if (STATUS_BYTE(5) != UDEKS_XCLOCK_READY ||
        udeks_vic_graphics_is_active() == 0 ||
        *(volatile unsigned char *)(UDEKS_TIME_STATUS_BASE + 5u) !=
            UDEKS_TIME_READY) {
        return UDEKS_XCLOCK_NOT_READY;
    }
    STATUS_BYTE(5) = UDEKS_XCLOCK_RUNNING;
    full_repaint();
    return UDEKS_XCLOCK_OK;
}

unsigned char udeks_xclock_poll(void)
{
    if (STATUS_BYTE(5) != UDEKS_XCLOCK_RUNNING) {
        return UDEKS_XCLOCK_OK;
    }
    update_window_input();
    if (STATUS_BYTE(5) == UDEKS_XCLOCK_RUNNING) {
        update_time();
    }
    return UDEKS_XCLOCK_OK;
}

unsigned char udeks_xclock_stop(void)
{
    if (STATUS_BYTE(5) != UDEKS_XCLOCK_RUNNING) {
        return UDEKS_XCLOCK_NOT_READY;
    }
    dragging = 0;
    udeks_vic_bitmap_clear(UDEKS_VIC_COLOR_YELLOW);
    udeks_vic_bitmap_commit();
    STATUS_BYTE(5) = UDEKS_XCLOCK_READY;
    STATUS_BYTE(24) = 0;
    increment_counter(22u);
    return UDEKS_XCLOCK_OK;
}

unsigned char udeks_xclock_is_running(void)
{
    return STATUS_BYTE(5) == UDEKS_XCLOCK_RUNNING ? 1u : 0u;
}
