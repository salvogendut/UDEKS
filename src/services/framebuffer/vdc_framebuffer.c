/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/boot_console.h"
#include "udeks/capability.h"
#include "udeks/font.h"
#include "udeks/framebuffer.h"
#include "udeks/framebuffer_surface.h"
#include "udeks/root_console.h"
#include "udeks/theme.h"
#include "udeks/vdc.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_FRAMEBUFFER_STATUS_BASE + (offset)))

#define VDC_REGISTER_COUNT          37u
#define VDC_REG_VERTICAL_DISPLAYED  6u
#define VDC_REG_CURSOR_START        10u
#define VDC_REG_DISPLAY_HI          12u
#define VDC_REG_DISPLAY_LO          13u
#define VDC_REG_UPDATE_HI           18u
#define VDC_REG_UPDATE_LO           19u
#define VDC_REG_ATTRIBUTE_HI        20u
#define VDC_REG_ATTRIBUTE_LO        21u
#define VDC_REG_VERTICAL_SCROLL     24u
#define VDC_REG_HORIZONTAL_SCROLL   25u
#define VDC_REG_COLOR               26u
#define VDC_REG_DATA                31u

#define FRAMEBUFFER_ERROR_CAPABILITY  1u
#define FRAMEBUFFER_ERROR_SNAPSHOT    2u
#define FRAMEBUFFER_ERROR_CLEAR       3u
#define FRAMEBUFFER_ERROR_UPLOAD      4u
#define FRAMEBUFFER_ERROR_VERIFY      5u
#define FRAMEBUFFER_ERROR_MODE        6u
#define FRAMEBUFFER_ERROR_FONT        7u

#define FRAMEBUFFER_FLAG_CLEARED     0x01u
#define FRAMEBUFFER_FLAG_UPLOADED    0x02u
#define FRAMEBUFFER_FLAG_VERIFIED    0x04u
#define FRAMEBUFFER_FLAG_ACTIVE      0x08u
#define FRAMEBUFFER_FLAG_STATE_SAVED 0x10u
#define FRAMEBUFFER_FLAG_FONT_DRAWN   0x20u

#define FRAMEBUFFER_CHECKSUM_LO       21u
#define FRAMEBUFFER_CHECKSUM_HI       22u
#define FRAMEBUFFER_FLAGS             23u

#define CONSOLE_FRAME_X               96u
#define CONSOLE_FRAME_Y               8u
#define CONSOLE_FRAME_WIDTH           528u
#define CONSOLE_FRAME_HEIGHT          184u
#define CONSOLE_CONTENT_X             104u
#define CONSOLE_CONTENT_Y             16u

extern const unsigned char udeks_splash_bitmap[];
extern const unsigned char udeks_wordmark_bitmap[];

static unsigned char saved_registers[VDC_REGISTER_COUNT];
static unsigned int vdc_address;
static unsigned int splash_checksum;
static unsigned char splash_row;
static unsigned char splash_column;
static unsigned char register_index;
static unsigned int text_checksum;
static unsigned char dirty_row;
static unsigned char dirty_first;
static unsigned char dirty_last;
static unsigned char dirty_start;
static unsigned char framebuffer_active;
static unsigned char framebuffer_owned;
static unsigned char console_row;
static unsigned char console_column;

static unsigned char vdc_write_register(
    unsigned char reg, unsigned char value)
{
    if (udeks_vdc_select(reg) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return udeks_vdc_write_selected(value);
}

static unsigned char vdc_read_register(
    unsigned char reg, unsigned char *value)
{
    if (udeks_vdc_select(reg) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    *value = udeks_vdc_read_selected();
    return udeks_vdc_status;
}

static unsigned char vdc_set_address(unsigned int address)
{
    if (vdc_write_register(VDC_REG_UPDATE_HI,
                           (unsigned char)(address >> 8)) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return vdc_write_register(VDC_REG_UPDATE_LO, (unsigned char)address);
}

static unsigned char snapshot_registers(void)
{
    for (register_index = 0; register_index < VDC_REGISTER_COUNT;
         ++register_index) {
        if (vdc_read_register(register_index,
                              &saved_registers[register_index]) != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
    }
    return UDEKS_VDC_OK;
}

static void restore_display_state(void)
{
    vdc_write_register(VDC_REG_VERTICAL_DISPLAYED, 0);
    vdc_write_register(VDC_REG_HORIZONTAL_SCROLL,
                       saved_registers[VDC_REG_HORIZONTAL_SCROLL]);
    vdc_write_register(VDC_REG_DISPLAY_HI,
                       saved_registers[VDC_REG_DISPLAY_HI]);
    vdc_write_register(VDC_REG_DISPLAY_LO,
                       saved_registers[VDC_REG_DISPLAY_LO]);
    vdc_write_register(VDC_REG_ATTRIBUTE_HI,
                       saved_registers[VDC_REG_ATTRIBUTE_HI]);
    vdc_write_register(VDC_REG_ATTRIBUTE_LO,
                       saved_registers[VDC_REG_ATTRIBUTE_LO]);
    vdc_write_register(VDC_REG_COLOR, saved_registers[VDC_REG_COLOR]);
    vdc_write_register(VDC_REG_CURSOR_START,
                       saved_registers[VDC_REG_CURSOR_START]);
    vdc_write_register(VDC_REG_VERTICAL_SCROLL,
                       saved_registers[VDC_REG_VERTICAL_SCROLL]);
    vdc_write_register(VDC_REG_VERTICAL_DISPLAYED,
                       saved_registers[VDC_REG_VERTICAL_DISPLAYED]);
}

static unsigned char blank_display(void)
{
    unsigned char vertical_scroll;

    vertical_scroll = (unsigned char)(
        saved_registers[VDC_REG_VERTICAL_SCROLL] & 0x7Fu);
    if (vdc_write_register(VDC_REG_VERTICAL_DISPLAYED, 0) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_VERTICAL_SCROLL, vertical_scroll) !=
            UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return UDEKS_VDC_OK;
}

static unsigned char upload_complete_surface(void)
{
    udeks_vdc_block_address = 0;
    udeks_vdc_block_source = udeks_surface_data();
    udeks_vdc_block_length = UDEKS_FRAMEBUFFER_SIZE;
    if (udeks_vdc_write_block() != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    udeks_surface_clean_all();
    udeks_surface_set_dirty_tracking(1);
    return UDEKS_VDC_OK;
}

static unsigned char flush_surface(void)
{
    const unsigned char *surface;

    surface = udeks_surface_data();
    for (dirty_row = 0; dirty_row < UDEKS_FRAMEBUFFER_HEIGHT; ++dirty_row) {
        dirty_start = 0;
        while (udeks_surface_dirty_span(
                   dirty_row, dirty_start,
                   &dirty_first, &dirty_last) != 0) {
            vdc_address = (unsigned int)dirty_row * UDEKS_FRAMEBUFFER_STRIDE +
                dirty_first;
            udeks_vdc_block_address = vdc_address;
            udeks_vdc_block_source = surface + vdc_address;
            udeks_vdc_block_length =
                (unsigned int)(dirty_last - dirty_first) + 1u;
            if (udeks_vdc_write_block() != UDEKS_VDC_OK) {
                return UDEKS_VDC_TIMEOUT;
            }
            udeks_surface_clean_span(
                dirty_row, dirty_first, dirty_last);
            if (dirty_last + 1u >= UDEKS_FRAMEBUFFER_STRIDE) {
                break;
            }
            dirty_start = dirty_last + 1u;
        }
    }
    return UDEKS_VDC_OK;
}

static void compose_splash(void)
{
    udeks_surface_blit_packed(
        UDEKS_SPLASH_X_BYTES, UDEKS_SPLASH_Y,
        UDEKS_SPLASH_WIDTH_BYTES, UDEKS_SPLASH_HEIGHT,
        udeks_splash_bitmap);
    udeks_surface_blit_packed(
        UDEKS_WORDMARK_X_BYTES, UDEKS_WORDMARK_Y,
        UDEKS_WORDMARK_WIDTH_BYTES, UDEKS_WORDMARK_HEIGHT,
        udeks_wordmark_bitmap);
}

static unsigned char verify_splash(void)
{
    const unsigned char *source;
    unsigned char value;

    source = udeks_splash_bitmap;
    splash_checksum = 0;
    vdc_address = (unsigned int)(
        UDEKS_SPLASH_Y * UDEKS_FRAMEBUFFER_STRIDE + UDEKS_SPLASH_X_BYTES);
    for (splash_row = 0; splash_row < UDEKS_SPLASH_HEIGHT; ++splash_row) {
        if (vdc_set_address(vdc_address) != UDEKS_VDC_OK ||
            udeks_vdc_select(VDC_REG_DATA) != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
        for (splash_column = 0;
             splash_column < UDEKS_SPLASH_WIDTH_BYTES; ++splash_column) {
            value = udeks_vdc_read_selected();
            if (udeks_vdc_status != UDEKS_VDC_OK || value != *source) {
                return UDEKS_VDC_TIMEOUT;
            }
            splash_checksum += value;
            ++source;
        }
        vdc_address += UDEKS_FRAMEBUFFER_STRIDE;
    }
    return UDEKS_VDC_OK;
}

static unsigned char activate_bitmap_mode(void)
{
    unsigned char bitmap_mode;
    unsigned char cursor_off;

    bitmap_mode = (unsigned char)(
        0x80u | (saved_registers[VDC_REG_HORIZONTAL_SCROLL] & 0x0Fu));
    cursor_off = (unsigned char)(
        saved_registers[VDC_REG_CURSOR_START] | 0x20u);

    if (vdc_write_register(VDC_REG_VERTICAL_DISPLAYED, 0) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_DISPLAY_HI, 0) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_DISPLAY_LO, 0) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_ATTRIBUTE_HI, 0) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_ATTRIBUTE_LO, 0) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_COLOR, UDEKS_THEME_VDC_COLOR) !=
            UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_CURSOR_START, cursor_off) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_HORIZONTAL_SCROLL, bitmap_mode) !=
            UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_VERTICAL_DISPLAYED,
                           saved_registers[VDC_REG_VERTICAL_DISPLAYED]) !=
            UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    STATUS_BYTE(12) = bitmap_mode;
    return UDEKS_VDC_OK;
}

static unsigned char compose_boot_console(void)
{
    const unsigned char *row_text;
    unsigned int cursor_x;
    unsigned char cursor_y;

    if (udeks_boot_console_build() != UDEKS_ROOT_CONSOLE_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    text_checksum = 0;
    for (console_row = 0; console_row < UDEKS_ROOT_CONSOLE_ROWS;
         ++console_row) {
        row_text = udeks_root_console_row(console_row);
        for (console_column = 0;
            console_column < UDEKS_ROOT_CONSOLE_COLUMNS;
             ++console_column) {
            if (row_text[console_column] != ' ') {
                text_checksum += row_text[console_column];
                if (udeks_surface_draw_char(
                        CONSOLE_CONTENT_X +
                            (unsigned int)console_column *
                                UDEKS_FONT_CELL_WIDTH,
                        (unsigned char)(CONSOLE_CONTENT_Y +
                            console_row * UDEKS_FONT_CELL_HEIGHT),
                        row_text[console_column]) !=
                    UDEKS_FRAMEBUFFER_OK) {
                    return UDEKS_VDC_TIMEOUT;
                }
            }
        }
    }
    if (udeks_surface_hline(
            CONSOLE_FRAME_X, CONSOLE_FRAME_Y,
            CONSOLE_FRAME_WIDTH, 1) != UDEKS_FRAMEBUFFER_OK ||
        udeks_surface_hline(
            CONSOLE_FRAME_X,
            CONSOLE_FRAME_Y + CONSOLE_FRAME_HEIGHT - 1u,
            CONSOLE_FRAME_WIDTH, 1) != UDEKS_FRAMEBUFFER_OK ||
        udeks_surface_fill_rect(
            CONSOLE_FRAME_X, CONSOLE_FRAME_Y, 1,
            CONSOLE_FRAME_HEIGHT, 1) != UDEKS_FRAMEBUFFER_OK ||
        udeks_surface_fill_rect(
            CONSOLE_FRAME_X + CONSOLE_FRAME_WIDTH - 1u,
            CONSOLE_FRAME_Y, 1, CONSOLE_FRAME_HEIGHT,
            1) != UDEKS_FRAMEBUFFER_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    if (udeks_root_console_cursor_visible() != 0) {
        cursor_x = CONSOLE_CONTENT_X +
            (unsigned int)udeks_root_console_cursor_column() *
                UDEKS_FONT_CELL_WIDTH;
        cursor_y = (unsigned char)(CONSOLE_CONTENT_Y +
            udeks_root_console_cursor_row() * UDEKS_FONT_CELL_HEIGHT);
        if (udeks_surface_fill_rect(
                cursor_x, cursor_y, UDEKS_FONT_CELL_WIDTH,
                UDEKS_FONT_CELL_HEIGHT, 1) != UDEKS_FRAMEBUFFER_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
    }
    return UDEKS_VDC_OK;
}

static unsigned char framebuffer_client_ready(void)
{
    if (framebuffer_active == 0) {
        return UDEKS_FRAMEBUFFER_NOT_READY;
    }
    if (framebuffer_owned == 0) {
        return UDEKS_FRAMEBUFFER_NOT_OWNER;
    }
    return UDEKS_FRAMEBUFFER_OK;
}

unsigned char udeks_framebuffer_acquire(void)
{
    if (framebuffer_active == 0) {
        return UDEKS_FRAMEBUFFER_NOT_READY;
    }
    if (framebuffer_owned != 0) {
        return UDEKS_FRAMEBUFFER_BUSY;
    }
    framebuffer_owned = 1;
    return UDEKS_FRAMEBUFFER_OK;
}

unsigned char udeks_framebuffer_release(void)
{
    unsigned char result;

    result = framebuffer_client_ready();
    if (result != UDEKS_FRAMEBUFFER_OK) {
        return result;
    }
    result = udeks_framebuffer_flush();
    if (result == UDEKS_FRAMEBUFFER_OK) {
        framebuffer_owned = 0;
    }
    return result;
}

unsigned char udeks_framebuffer_plot(
    unsigned int x, unsigned char y, unsigned char set)
{
    unsigned char result;

    result = framebuffer_client_ready();
    if (result != UDEKS_FRAMEBUFFER_OK) {
        return result;
    }
    return udeks_surface_plot(x, y, set);
}

unsigned char udeks_framebuffer_hline(
    unsigned int x, unsigned char y, unsigned int width, unsigned char set)
{
    unsigned char result;

    result = framebuffer_client_ready();
    if (result != UDEKS_FRAMEBUFFER_OK) {
        return result;
    }
    return udeks_surface_hline(x, y, width, set);
}

unsigned char udeks_framebuffer_fill_rect(
    unsigned int x, unsigned char y, unsigned int width,
    unsigned int height, unsigned char set)
{
    unsigned char result;

    result = framebuffer_client_ready();
    if (result != UDEKS_FRAMEBUFFER_OK) {
        return result;
    }
    return udeks_surface_fill_rect(x, y, width, height, set);
}

unsigned char udeks_framebuffer_draw_char(
    unsigned int x, unsigned char y, unsigned char character)
{
    unsigned char result;

    result = framebuffer_client_ready();
    if (result != UDEKS_FRAMEBUFFER_OK) {
        return result;
    }
    return udeks_surface_draw_char(x, y, character);
}

unsigned char udeks_framebuffer_draw_text(
    unsigned int x, unsigned char y, const unsigned char *text)
{
    unsigned char result;

    result = framebuffer_client_ready();
    if (result != UDEKS_FRAMEBUFFER_OK) {
        return result;
    }
    return udeks_surface_draw_text(x, y, text);
}

unsigned char udeks_framebuffer_flush(void)
{
    unsigned char result;

    result = framebuffer_client_ready();
    if (result != UDEKS_FRAMEBUFFER_OK) {
        return result;
    }
    if (flush_surface() != UDEKS_VDC_OK) {
        return UDEKS_FRAMEBUFFER_IO_ERROR;
    }
    return UDEKS_FRAMEBUFFER_OK;
}

static unsigned char framebuffer_fail(unsigned char code)
{
    framebuffer_active = 0;
    framebuffer_owned = 0;
    if ((STATUS_BYTE(FRAMEBUFFER_FLAGS) & FRAMEBUFFER_FLAG_STATE_SAVED) != 0) {
        restore_display_state();
    }
    STATUS_BYTE(6) = code;
    STATUS_BYTE(5) = (unsigned char)(UDEKS_FRAMEBUFFER_STATE_ERROR | code);
    return code;
}

static void status_begin(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_FRAMEBUFFER_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'V';
    STATUS_BYTE(1) = 'F';
    STATUS_BYTE(2) = 'B';
    STATUS_BYTE(3) = 'R';
    STATUS_BYTE(4) = 8;
    STATUS_BYTE(5) = UDEKS_FRAMEBUFFER_STATE_STARTING;
    STATUS_BYTE(7) = UDEKS_FRAMEBUFFER_STRIDE;
    STATUS_BYTE(8) = UDEKS_FRAMEBUFFER_HEIGHT;
    STATUS_BYTE(9) = 1;
    STATUS_BYTE(15) = UDEKS_SPLASH_WIDTH_BYTES;
    STATUS_BYTE(16) = UDEKS_SPLASH_HEIGHT;
    STATUS_BYTE(17) = UDEKS_SPLASH_X_BYTES;
    STATUS_BYTE(18) = UDEKS_SPLASH_Y;
    vdc_address = (unsigned int)(
        UDEKS_SPLASH_Y * UDEKS_FRAMEBUFFER_STRIDE + UDEKS_SPLASH_X_BYTES);
    STATUS_BYTE(19) = (unsigned char)vdc_address;
    STATUS_BYTE(20) = (unsigned char)(vdc_address >> 8);
    STATUS_BYTE(24) = UDEKS_THEME_VDC_COLOR;
    STATUS_BYTE(25) = UDEKS_FONT_WIDTH;
    STATUS_BYTE(26) = UDEKS_FONT_HEIGHT;
    STATUS_BYTE(27) = UDEKS_BOOT_CONSOLE_LINES;
    STATUS_BYTE(30) = 0x1F;
    STATUS_BYTE(31) = UDEKS_FRAMEBUFFER_API_FLAGS;
}

unsigned char udeks_framebuffer_start(void)
{
    framebuffer_active = 0;
    framebuffer_owned = 0;
    status_begin();
    if (STATUS_BYTE(0) != 'V' || STATUS_BYTE(1) != 'F' ||
        STATUS_BYTE(2) != 'B' || STATUS_BYTE(3) != 'R' ||
        (*(volatile unsigned char *)(UDEKS_CAPABILITY_STATUS_BASE + 5u)) !=
            UDEKS_CAPABILITY_STATE_READY) {
        return framebuffer_fail(FRAMEBUFFER_ERROR_CAPABILITY);
    }
    STATUS_BYTE(10) =
        *(volatile unsigned char *)(UDEKS_CAPABILITY_STATUS_BASE + 10u);

    if (snapshot_registers() != UDEKS_VDC_OK) {
        return framebuffer_fail(FRAMEBUFFER_ERROR_SNAPSHOT);
    }
    STATUS_BYTE(11) = saved_registers[VDC_REG_HORIZONTAL_SCROLL];
    STATUS_BYTE(13) = saved_registers[VDC_REG_DISPLAY_HI];
    STATUS_BYTE(14) = saved_registers[VDC_REG_DISPLAY_LO];
    STATUS_BYTE(FRAMEBUFFER_FLAGS) |= FRAMEBUFFER_FLAG_STATE_SAVED;

    if (blank_display() != UDEKS_VDC_OK) {
        return framebuffer_fail(FRAMEBUFFER_ERROR_CLEAR);
    }
    udeks_surface_reset();
    udeks_surface_set_dirty_tracking(0);
    STATUS_BYTE(FRAMEBUFFER_FLAGS) |= FRAMEBUFFER_FLAG_CLEARED;
    compose_splash();
    if (compose_boot_console() != UDEKS_VDC_OK) {
        return framebuffer_fail(FRAMEBUFFER_ERROR_FONT);
    }
    STATUS_BYTE(28) = (unsigned char)text_checksum;
    STATUS_BYTE(29) = (unsigned char)(text_checksum >> 8);
    STATUS_BYTE(FRAMEBUFFER_FLAGS) |= FRAMEBUFFER_FLAG_FONT_DRAWN;
    if (upload_complete_surface() != UDEKS_VDC_OK) {
        return framebuffer_fail(FRAMEBUFFER_ERROR_UPLOAD);
    }
    STATUS_BYTE(FRAMEBUFFER_FLAGS) |= FRAMEBUFFER_FLAG_UPLOADED;
    if (verify_splash() != UDEKS_VDC_OK) {
        return framebuffer_fail(FRAMEBUFFER_ERROR_VERIFY);
    }
    STATUS_BYTE(FRAMEBUFFER_CHECKSUM_LO) = (unsigned char)splash_checksum;
    STATUS_BYTE(FRAMEBUFFER_CHECKSUM_HI) =
        (unsigned char)(splash_checksum >> 8);
    STATUS_BYTE(FRAMEBUFFER_FLAGS) |= FRAMEBUFFER_FLAG_VERIFIED;
    if (activate_bitmap_mode() != UDEKS_VDC_OK) {
        return framebuffer_fail(FRAMEBUFFER_ERROR_MODE);
    }
    STATUS_BYTE(FRAMEBUFFER_FLAGS) |= FRAMEBUFFER_FLAG_ACTIVE;
    framebuffer_active = 1;
    STATUS_BYTE(5) = UDEKS_FRAMEBUFFER_STATE_READY;
    return 0;
}
