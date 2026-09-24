/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mailbox.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"
#include "udeks/xwave.h"
#include "udeks/z80_worker.h"

#pragma code-name(push, "APP2CODE")
#pragma rodata-name(push, "APP2RODATA")

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_XWAVE_STATUS_BASE + (offset)))
#define SAMPLE_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_WAVE_BUFFER_BASE + (offset)))

#define WINDOW_X       144u
#define WINDOW_Y       88u
#define WINDOW_WIDTH   168u
#define WINDOW_HEIGHT  104u
#define WINDOW_OWNER   2u
#define PLOT_SAMPLES   64u
#define PLOT_X_STEP    2u

static const signed char sine64[64] = {
      0,  3,  6,  9, 12, 14, 17, 19, 21, 23, 25, 26, 28, 29, 29, 30,
     30, 30, 29, 29, 28, 26, 25, 23, 21, 19, 17, 14, 12,  9,  6,  3,
      0, -3, -6, -9,-12,-14,-17,-19,-21,-23,-25,-26,-28,-29,-29,-30,
    -30,-30,-29,-29,-28,-26,-25,-23,-21,-19,-17,-14,-12, -9, -6, -3
};
static const unsigned char window_title[] = "XWAVE";

#pragma bss-name(push, "APP2BSS")
static unsigned char window_handle;
static unsigned int window_x;
static unsigned char window_y;
static unsigned int window_width;
static unsigned char window_height;
static unsigned char wave_phase;
#pragma bss-name(pop)

static void increment_counter(unsigned char offset)
{
    ++STATUS_BYTE(offset);
    if (STATUS_BYTE(offset) == 0) {
        ++STATUS_BYTE(offset + 1u);
    }
}

static unsigned char sample_batch(unsigned char phase, unsigned char count)
{
    unsigned int next_phase;
    unsigned char index;

    if (udeks_z80_submit(
            UDEKS_MB_OP_WAVE_SAMPLES, phase, 2u, count,
            &next_phase) == UDEKS_Z80_OK) {
        increment_counter(12u);
        return (unsigned char)next_phase;
    }
    for (index = 0; index < count; ++index) {
        SAMPLE_BYTE(index) = (unsigned char)sine64[phase >> 2];
        phase += 2u;
    }
    increment_counter(14u);
    return phase;
}

static void paint_wave(unsigned char handle)
{
    unsigned char remaining;
    unsigned char count;
    unsigned char index;
    unsigned char phase;
    signed char sample;
    int center_y;
    int plot_x;
    int plot_y;
    int previous_x;
    int previous_y;

    if (udeks_window_get_geometry(
            handle, &window_x, &window_y,
            &window_width, &window_height) != UDEKS_WINDOW_OK) {
        return;
    }
    center_y = window_y + UDEKS_WINDOW_TITLE_HEIGHT +
        (window_height - UDEKS_WINDOW_TITLE_HEIGHT) / 2u;
    udeks_vic_bitmap_line(
        window_x + 4, center_y,
        window_x + window_width - 5, center_y,
        UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_line(
        window_x + 8, window_y + UDEKS_WINDOW_TITLE_HEIGHT + 4,
        window_x + 8, window_y + window_height - 5,
        UDEKS_VIC_COLOR_BLACK);

    remaining = window_width > 136u ? PLOT_SAMPLES :
        (unsigned char)((window_width - 8u) / PLOT_X_STEP);
    phase = wave_phase;
    plot_x = window_x + 4;
    previous_x = plot_x;
    previous_y = center_y;
    while (remaining != 0) {
        count = remaining > UDEKS_WAVE_BUFFER_SIZE ?
            UDEKS_WAVE_BUFFER_SIZE : remaining;
        phase = sample_batch(phase, count);
        for (index = 0; index < count; ++index) {
            sample = (signed char)SAMPLE_BYTE(index);
            plot_y = center_y - sample;
            udeks_vic_bitmap_line(
                previous_x, previous_y, plot_x, plot_y,
                UDEKS_VIC_COLOR_BLACK);
            previous_x = plot_x;
            plot_x += PLOT_X_STEP;
            previous_y = plot_y;
        }
        remaining -= count;
    }
    STATUS_BYTE(8) = window_handle;
    STATUS_BYTE(9) = wave_phase;
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
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_XWAVE_READY;
    STATUS_BYTE(7) = 0x07u;
    window_handle = UDEKS_WINDOW_NONE;
    wave_phase = 0;
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

#pragma rodata-name(pop)
#pragma code-name(pop)
