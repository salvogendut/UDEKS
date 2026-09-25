/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/time.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"
#include "udeks/xclock.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_XCLOCK_STATUS_BASE + (offset)))

#define WINDOW_WIDTH       72u
#define WINDOW_HEIGHT      77u
#define WINDOW_INITIAL_X   124u
#define WINDOW_INITIAL_Y   61u
#define WINDOW_OWNER       1u

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

static const unsigned char window_title[] = "XCLOCK";

static unsigned char window_handle;
static unsigned int window_x;
static unsigned char window_y;
static unsigned int window_width;
static unsigned char window_height;
static unsigned int face_x;
static unsigned char face_y;
static unsigned char face_radius;
static unsigned char previous_hour;
static unsigned char previous_minute;

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static void publish_geometry(void)
{
    if (window_handle != UDEKS_WINDOW_NONE) {
        udeks_window_get_geometry(
            window_handle, &window_x, &window_y,
            &window_width, &window_height);
    }
    STATUS_BYTE(8) = window_x;
    STATUS_BYTE(9) = window_y;
    STATUS_BYTE(10) = (unsigned char)window_width;
    STATUS_BYTE(11) = window_height;
    STATUS_BYTE(24) = udeks_window_is_dragging(window_handle);
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

    x = window_x + (window_width - 19u) / 2u;
    y = window_y + window_height - 11u;
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
    draw_hand(hour_position(hour, minute), face_radius / 2u, color);
    draw_hand(minute,
        face_radius - face_radius / 4u, color);
}

static void draw_face(void)
{
    unsigned char position;
    unsigned char next;

    for (position = 0; position < 60u; position += 2u) {
        next = (unsigned char)((position + 2u) % 60u);
        udeks_vic_bitmap_line(
            point_x(position, face_radius), point_y(position, face_radius),
            point_x(next, face_radius), point_y(next, face_radius),
            UDEKS_VIC_COLOR_BLACK);
    }
    for (position = 0; position < 60u; position += 5u) {
        udeks_vic_bitmap_line(
            point_x(position, face_radius), point_y(position, face_radius),
            point_x(position, face_radius - 3u),
            point_y(position, face_radius - 3u),
            UDEKS_VIC_COLOR_BLACK);
    }
}

static void paint_clock(unsigned char handle)
{
    unsigned char hour;
    unsigned char minute;
    unsigned char second;

    if (udeks_window_get_geometry(
            handle, &window_x, &window_y,
            &window_width, &window_height) != UDEKS_WINDOW_OK) {
        return;
    }
    udeks_time_now(&hour, &minute, &second);
    face_x = window_x + window_width / 2u;
    face_radius = (unsigned char)((window_width - 8u) / 2u);
    if (face_radius >
            (window_height - UDEKS_WINDOW_TITLE_HEIGHT - 18u) / 2u) {
        face_radius = (unsigned char)(
            (window_height - UDEKS_WINDOW_TITLE_HEIGHT - 18u) / 2u);
    }
    if (face_radius < 4u) {
        face_radius = 4u;
    }
    face_y = (unsigned char)(
        window_y + UDEKS_WINDOW_TITLE_HEIGHT + 3u + face_radius);
    draw_face();
    draw_hands(hour, minute, UDEKS_VIC_COLOR_BLACK);
    draw_digital(hour, minute);
    previous_hour = hour;
    previous_minute = minute;
    STATUS_BYTE(12) = hour;
    STATUS_BYTE(13) = minute;
    STATUS_BYTE(14) = second;
    STATUS_BYTE(25) = face_radius;
    increment_counter(16u);
    if ((unsigned char)window_x != STATUS_BYTE(8) ||
        window_y != STATUS_BYTE(9)) {
        increment_counter(20u);
    }
    publish_geometry();
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
    if (udeks_window_repaint(window_handle) == UDEKS_WINDOW_OK &&
        hour == previous_hour && minute == previous_minute) {
        increment_counter(18u);
    }
}

static void close_clock(unsigned char handle)
{
    (void)handle;
    window_handle = UDEKS_WINDOW_NONE;
    STATUS_BYTE(5) = UDEKS_XCLOCK_READY;
    STATUS_BYTE(24) = 0;
    increment_counter(22u);
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
    STATUS_BYTE(4) = 2;
    STATUS_BYTE(5) = UDEKS_XCLOCK_READY;
    STATUS_BYTE(7) = 0x07u;
    window_handle = UDEKS_WINDOW_NONE;
    window_x = WINDOW_INITIAL_X;
    window_y = WINDOW_INITIAL_Y;
    window_width = WINDOW_WIDTH;
    window_height = WINDOW_HEIGHT;
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
    window_handle = udeks_window_create(
        WINDOW_OWNER, UDEKS_WINDOW_SURFACE_BITMAP,
        UDEKS_WINDOW_FLAG_MOVABLE | UDEKS_WINDOW_FLAG_CLOSABLE,
        WINDOW_INITIAL_X, WINDOW_INITIAL_Y,
        WINDOW_WIDTH, WINDOW_HEIGHT, window_title,
        paint_clock, close_clock);
    if (window_handle == UDEKS_WINDOW_NONE) {
        STATUS_BYTE(5) = UDEKS_XCLOCK_READY;
        return UDEKS_XCLOCK_NOT_READY;
    }
    publish_geometry();
    return UDEKS_XCLOCK_OK;
}

unsigned char udeks_xclock_poll(void)
{
    if (STATUS_BYTE(5) != UDEKS_XCLOCK_RUNNING) {
        return UDEKS_XCLOCK_OK;
    }
    publish_geometry();
    if (STATUS_BYTE(5) == UDEKS_XCLOCK_RUNNING &&
        udeks_window_is_dragging(window_handle) == 0) {
        update_time();
    }
    return UDEKS_XCLOCK_OK;
}

unsigned char udeks_xclock_stop(void)
{
    if (STATUS_BYTE(5) != UDEKS_XCLOCK_RUNNING) {
        return UDEKS_XCLOCK_NOT_READY;
    }
    if (udeks_window_destroy(window_handle) != UDEKS_WINDOW_OK) {
        return UDEKS_XCLOCK_NOT_READY;
    }
    return UDEKS_XCLOCK_OK;
}

unsigned char udeks_xclock_is_running(void)
{
    return STATUS_BYTE(5) == UDEKS_XCLOCK_RUNNING ? 1u : 0u;
}

unsigned char udeks_xclock_is_focused(void)
{
    return window_handle != UDEKS_WINDOW_NONE &&
        udeks_window_is_focused(window_handle) != 0 ? 1u : 0u;
}
