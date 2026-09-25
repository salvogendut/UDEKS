/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mailbox.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"
#include "udeks/xwave.h"
#include "udeks/z80_worker.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_XWAVE_STATUS_BASE + (offset)))
#define SAMPLE_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_WAVE_BUFFER_BASE + (offset)))
#define PREVIOUS_HEIGHT_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_XWAVE_ROW_BASE + (offset)))

#define WINDOW_X             144u
#define WINDOW_Y              88u
#define WINDOW_WIDTH         168u
#define WINDOW_HEIGHT        104u
#define WINDOW_OWNER           2u
#define SURFACE_ROWS          21u
#define SURFACE_COLUMNS       25u
#define SURFACE_SAMPLES      525u
#define PROJECTED_WIDTH      176u
#define PROJECTED_HEIGHT      75u

/* 40 * sinc(r), sampled every half unit from r=0 through r=17. */
static const signed char sinc_height[35] = {
    40, 38, 34, 27, 18, 10,  2, -4, -8, -9, -8, -5,
    -2,  1,  4,  5,  5,  4,  2,  0, -2, -3, -4, -3,
    -2,  0,  1,  2,  3,  3,  2,  1, -1, -2, -2
};
static const unsigned char window_title[] = "XWAVE";

static unsigned char window_handle;
static unsigned int window_x;
static unsigned char window_y;
static unsigned int window_width;
static unsigned char window_height;
static unsigned char surface_cache[SURFACE_SAMPLES];
static unsigned char surface_cache_valid;
static unsigned int surface_cache_width;
static unsigned char surface_cache_height;

static void increment_counter(unsigned char offset)
{
    ++STATUS_BYTE(offset);
    if (STATUS_BYTE(offset) == 0) {
        ++STATUS_BYTE(offset + 1u);
    }
}

static signed char local_surface_height(
    unsigned char row, unsigned char column)
{
    unsigned char x;
    unsigned char y;
    unsigned char greater;
    unsigned char lesser;
    unsigned char radius;

    x = column > 12u ? column - 12u : 12u - column;
    y = row > 10u ? row - 10u : 10u - row;
    x *= 5u;
    y *= 6u;
    if (x > y) {
        greater = x;
        lesser = y;
    } else {
        greater = y;
        lesser = x;
    }
    radius = (unsigned char)(greater + (lesser >> 2) + (lesser >> 3));
    radius = (unsigned char)((radius * 2u + 2u) / 5u);
    if (radius > 34u) {
        radius = 34u;
    }
    return sinc_height[radius];
}

static void sample_row(unsigned char row)
{
    unsigned int next_row;
    unsigned char column;

    if (udeks_z80_submit(
            UDEKS_MB_OP_SURFACE_ROWS, row, 1u, SURFACE_COLUMNS,
            &next_row) == UDEKS_Z80_OK &&
        next_row == row + 1u) {
        increment_counter(12u);
        return;
    }
    for (column = 0; column < SURFACE_COLUMNS; ++column) {
        SAMPLE_BYTE(column) =
            (unsigned char)local_surface_height(row, column);
    }
    increment_counter(14u);
}

static int project_x(int local_x)
{
    return window_x + 3u +
        (unsigned int)local_x *
            (window_width - 6u) / PROJECTED_WIDTH;
}

static int project_y(int local_y)
{
    return window_y + UDEKS_WINDOW_TITLE_HEIGHT + 1u +
        (unsigned int)local_y *
            (window_height - UDEKS_WINDOW_TITLE_HEIGHT - 5u) /
            PROJECTED_HEIGHT;
}

static void paint_wave(unsigned char handle)
{
    unsigned char row;
    unsigned char column;
    signed char previous_height;
    int local_x;
    int local_y;
    int previous_local_x;
    int previous_local_y;
    int plot_x;
    int plot_y;
    int previous_x;
    int previous_y;
    signed char height;
    unsigned int cache_offset;
    unsigned char refresh_samples;

    if (udeks_window_get_geometry(
            handle, &window_x, &window_y,
            &window_width, &window_height) != UDEKS_WINDOW_OK) {
        return;
    }

    refresh_samples = surface_cache_valid == 0 ||
        surface_cache_width != window_width ||
        surface_cache_height != window_height;
    cache_offset = 0;
    for (row = 0; row < SURFACE_ROWS; ++row) {
        if (refresh_samples != 0) {
            sample_row(row);
            for (column = 0; column < SURFACE_COLUMNS; ++column) {
                surface_cache[cache_offset + column] = SAMPLE_BYTE(column);
            }
        }
        previous_x = 0;
        previous_y = 0;
        for (column = 0; column < SURFACE_COLUMNS; ++column) {
            height = (signed char)surface_cache[cache_offset + column];
            local_x = (int)(column + SURFACE_ROWS - 1u - row) * 4;
            local_y = 28 + column + row - height;
            plot_x = project_x(local_x);
            plot_y = project_y(local_y);
            if (column != 0 && (row & 1u) == 0) {
                udeks_vic_bitmap_line(
                    previous_x, previous_y, plot_x, plot_y,
                    UDEKS_VIC_COLOR_BLACK);
            }
            if (row != 0 && (column & 1u) == 0) {
                previous_height =
                    (signed char)PREVIOUS_HEIGHT_BYTE(column);
                previous_local_x = local_x + 4;
                previous_local_y = 27 + column + row - previous_height;
                udeks_vic_bitmap_line(
                    project_x(previous_local_x),
                    project_y(previous_local_y),
                    plot_x, plot_y, UDEKS_VIC_COLOR_BLACK);
            }
            PREVIOUS_HEIGHT_BYTE(column) = (unsigned char)height;
            previous_x = plot_x;
            previous_y = plot_y;
        }
        cache_offset += SURFACE_COLUMNS;
    }
    if (refresh_samples != 0) {
        surface_cache_valid = 1;
        surface_cache_width = window_width;
        surface_cache_height = window_height;
    }
    STATUS_BYTE(8) = window_handle;
    STATUS_BYTE(9) = SURFACE_ROWS;
    STATUS_BYTE(10) = SURFACE_COLUMNS;
    STATUS_BYTE(11) = 2u;
    STATUS_BYTE(18) = (unsigned char)SURFACE_SAMPLES;
    STATUS_BYTE(19) = (unsigned char)(SURFACE_SAMPLES >> 8);
    STATUS_BYTE(20) = (unsigned char)window_x;
    STATUS_BYTE(21) = window_y;
    STATUS_BYTE(22) = (unsigned char)window_width;
    STATUS_BYTE(23) = window_height;
    increment_counter(16u);
}

static void close_wave(unsigned char handle)
{
    (void)handle;
    window_handle = UDEKS_WINDOW_NONE;
    STATUS_BYTE(5) = UDEKS_XWAVE_READY;
}

unsigned char udeks_xwave_initialize(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_XWAVE_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'X';
    STATUS_BYTE(1) = 'W';
    STATUS_BYTE(2) = 'A';
    STATUS_BYTE(3) = 'V';
    STATUS_BYTE(4) = 3;
    STATUS_BYTE(5) = UDEKS_XWAVE_READY;
    STATUS_BYTE(7) = 0x07u;
    window_handle = UDEKS_WINDOW_NONE;
    surface_cache_valid = 0;
    return UDEKS_XWAVE_OK;
}

unsigned char udeks_xwave_start(void)
{
    if (STATUS_BYTE(5) == UDEKS_XWAVE_RUNNING) {
        return UDEKS_XWAVE_ALREADY_RUNNING;
    }
    if (STATUS_BYTE(5) != UDEKS_XWAVE_READY ||
        udeks_vic_graphics_is_active() == 0) {
        return UDEKS_XWAVE_NOT_READY;
    }
    STATUS_BYTE(5) = UDEKS_XWAVE_RUNNING;
    window_handle = udeks_window_create(
        WINDOW_OWNER, UDEKS_WINDOW_SURFACE_BITMAP,
        UDEKS_WINDOW_FLAG_MOVABLE | UDEKS_WINDOW_FLAG_CLOSABLE,
        WINDOW_X, WINDOW_Y, WINDOW_WIDTH, WINDOW_HEIGHT,
        window_title, paint_wave, close_wave);
    if (window_handle == UDEKS_WINDOW_NONE) {
        STATUS_BYTE(5) = UDEKS_XWAVE_READY;
        return UDEKS_XWAVE_NOT_READY;
    }
    return UDEKS_XWAVE_OK;
}

unsigned char udeks_xwave_poll(void)
{
    if (STATUS_BYTE(5) != UDEKS_XWAVE_RUNNING) {
        return UDEKS_XWAVE_OK;
    }
    STATUS_BYTE(24) = udeks_window_is_dragging(window_handle);
    STATUS_BYTE(25) = udeks_window_is_focused(window_handle);
    return UDEKS_XWAVE_OK;
}

unsigned char udeks_xwave_stop(void)
{
    if (STATUS_BYTE(5) != UDEKS_XWAVE_RUNNING ||
        udeks_window_destroy(window_handle) != UDEKS_WINDOW_OK) {
        return UDEKS_XWAVE_NOT_READY;
    }
    return UDEKS_XWAVE_OK;
}

unsigned char udeks_xwave_is_running(void)
{
    return STATUS_BYTE(5) == UDEKS_XWAVE_RUNNING ? 1u : 0u;
}

unsigned char udeks_xwave_is_focused(void)
{
    return udeks_window_is_focused(window_handle);
}
