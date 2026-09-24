/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/boot_console.h"
#include "udeks/console.h"
#include "udeks/root_console.h"
#include "udeks/theme.h"
#include "udeks/vdc.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_CONSOLE_STATUS_BASE + (offset)))

#define VDC_REG_CURSOR_START       10u
#define VDC_REG_CURSOR_END         11u
#define VDC_REG_DISPLAY_HI         12u
#define VDC_REG_DISPLAY_LO         13u
#define VDC_REG_CURSOR_HI          14u
#define VDC_REG_CURSOR_LO          15u
#define VDC_REG_UPDATE_HI          18u
#define VDC_REG_UPDATE_LO          19u
#define VDC_REG_ATTRIBUTE_HI       20u
#define VDC_REG_ATTRIBUTE_LO       21u
#define VDC_REG_VERTICAL_SCROLL    24u
#define VDC_REG_HORIZONTAL_SCROLL  25u
#define VDC_REG_COLOR              26u
#define VDC_REG_CHARACTER_HI       28u
#define VDC_REG_BLOCK_SIZE         30u
#define VDC_REG_DATA               31u

#define SCREEN_BASE                0x0000u
#define ATTRIBUTE_BASE             0x0800u
#define SCREEN_ATTRIBUTE           UDEKS_THEME_VDC_ATTRIBUTE
#define SCREEN_ATTRIBUTE_ALT       0x80u
#define SCREEN_WIDTH               UDEKS_CONSOLE_COLUMNS
#define SCREEN_HEIGHT              UDEKS_CONSOLE_ROWS

#define ASSET_HEADER_SIZE          16u
#define ASSET_GLYPH_COUNT          5u
#define ASSET_PIPE_WIDTH           6u
#define ASSET_PIPE_HEIGHT          7u
#define ASSET_WORD_WIDTH           8u
#define ASSET_WORD_HEIGHT          9u
#define ASSET_BORDER_TL            10u
#define ASSET_BORDER_TR            11u
#define ASSET_BORDER_BL            12u
#define ASSET_BORDER_BR            13u
#define ASSET_BORDER_H             14u
#define ASSET_BORDER_V             15u

#define LOGO_X                     2u
#define LOGO_Y                     1u
#define WORDMARK_X                 2u
#define WORDMARK_Y                 10u
#define FRAME_LEFT                 (UDEKS_CONSOLE_ROOT_X - 1u)
#define FRAME_TOP                  (UDEKS_CONSOLE_ROOT_Y - 1u)
#define FRAME_RIGHT                \
    (UDEKS_CONSOLE_ROOT_X + UDEKS_ROOT_CONSOLE_COLUMNS)
#define FRAME_BOTTOM               \
    (UDEKS_CONSOLE_ROOT_Y + UDEKS_ROOT_CONSOLE_ROWS)

extern const unsigned char udeks_vdc_text_assets[];

static unsigned char address_high;
static unsigned char address_low;
static unsigned char service_failure;
static unsigned char row_buffer[UDEKS_ROOT_CONSOLE_COLUMNS];
static unsigned char attribute_buffer[UDEKS_ROOT_CONSOLE_COLUMNS];
static unsigned char frame_buffer[UDEKS_ROOT_CONSOLE_COLUMNS + 2u];

static void status_begin(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_CONSOLE_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'V';
    STATUS_BYTE(1) = 'C';
    STATUS_BYTE(2) = 'O';
    STATUS_BYTE(3) = 'N';
    STATUS_BYTE(4) = 2;
    STATUS_BYTE(5) = UDEKS_CONSOLE_STATE_STARTING;
    STATUS_BYTE(7) = SCREEN_WIDTH;
    STATUS_BYTE(8) = SCREEN_HEIGHT;
    STATUS_BYTE(9) = SCREEN_ATTRIBUTE;
    STATUS_BYTE(10) = (unsigned char)(SCREEN_BASE >> 8);
    STATUS_BYTE(11) = (unsigned char)(ATTRIBUTE_BASE >> 8);
}

static unsigned char vdc_register_write(
    unsigned char reg, unsigned char value)
{
    if (udeks_vdc_select(reg) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return udeks_vdc_write_selected(value);
}

static unsigned char vdc_register_read(unsigned char reg)
{
    if (udeks_vdc_select(reg) != UDEKS_VDC_OK) {
        return 0;
    }
    return udeks_vdc_read_selected();
}

static unsigned char vdc_set_update(void)
{
    if (vdc_register_write(VDC_REG_UPDATE_HI, address_high) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return vdc_register_write(VDC_REG_UPDATE_LO, address_low);
}

static unsigned char vdc_begin_memory(void)
{
    if (vdc_set_update() != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return udeks_vdc_select(VDC_REG_DATA);
}

static unsigned char vdc_fill(
    unsigned int address, unsigned char value, unsigned int length)
{
    unsigned char vertical_scroll;
    unsigned char count;

    vertical_scroll = vdc_register_read(VDC_REG_VERTICAL_SCROLL);
    if (udeks_vdc_status != UDEKS_VDC_OK ||
        vdc_register_write(
            VDC_REG_VERTICAL_SCROLL,
            (unsigned char)(vertical_scroll & 0x7Fu)) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    while (length != 0) {
        address_high = (unsigned char)(address >> 8);
        address_low = (unsigned char)address;
        if (vdc_begin_memory() != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
        if (udeks_vdc_write_selected(value) != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
        if (length >= 256u) {
            count = 255u;
            length -= 256u;
            address += 256u;
        } else {
            count = (unsigned char)(length - 1u);
            address += length;
            length = 0;
        }
        if (vdc_register_write(VDC_REG_BLOCK_SIZE, count) != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
    }
    return UDEKS_VDC_OK;
}

static unsigned char screen_code(unsigned char value)
{
    if (value >= 'A' && value <= 'Z') {
        return (unsigned char)(value - 'A' + 1u);
    }
    if (value >= 'a' && value <= 'z') {
        return (unsigned char)(value - 'a' + 1u);
    }
    if (value >= '@' && value <= '_') {
        return (unsigned char)(value - '@');
    }
    return value;
}

static unsigned char vdc_write_block_at(
    unsigned int address, const unsigned char *source, unsigned int length)
{
    udeks_vdc_block_address = address;
    udeks_vdc_block_source = source;
    udeks_vdc_block_length = length;
    return udeks_vdc_write_block();
}

static unsigned char upload_custom_glyphs(void)
{
    unsigned char character_register;
    unsigned int address;
    unsigned int length;

    if (udeks_vdc_text_assets[0] != 'V' ||
        udeks_vdc_text_assets[1] != 'T' ||
        udeks_vdc_text_assets[2] != 'G' ||
        udeks_vdc_text_assets[3] != '1' ||
        udeks_vdc_text_assets[4] != 1u) {
        return UDEKS_VDC_TIMEOUT;
    }
    character_register = vdc_register_read(VDC_REG_CHARACTER_HI);
    if (udeks_vdc_status != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    address = (unsigned int)(character_register & 0xE0u) << 8;
    address += 0x0800u;
    length = (unsigned int)udeks_vdc_text_assets[ASSET_GLYPH_COUNT] * 16u;
    STATUS_BYTE(17) = udeks_vdc_text_assets[ASSET_GLYPH_COUNT];
    STATUS_BYTE(18) = (unsigned char)(address >> 8);
    return vdc_write_block_at(
        address, udeks_vdc_text_assets + ASSET_HEADER_SIZE, length);
}

static const unsigned char *pipe_map(void)
{
    return udeks_vdc_text_assets + ASSET_HEADER_SIZE +
        (unsigned int)udeks_vdc_text_assets[ASSET_GLYPH_COUNT] * 16u;
}

static const unsigned char *wordmark_map(void)
{
    return pipe_map() +
        (unsigned int)udeks_vdc_text_assets[ASSET_PIPE_WIDTH] *
        udeks_vdc_text_assets[ASSET_PIPE_HEIGHT];
}

static unsigned char draw_tile_map(
    unsigned char x, unsigned char y,
    unsigned char width, unsigned char height,
    const unsigned char *map)
{
    unsigned char row;

    for (row = 0; row < height; ++row) {
        if (vdc_write_block_at(
                (unsigned int)(y + row) * SCREEN_WIDTH + x,
                map + (unsigned int)row * width, width) != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
    }
    return UDEKS_VDC_OK;
}

static unsigned char draw_logo(void)
{
    if (draw_tile_map(
            LOGO_X, LOGO_Y,
            udeks_vdc_text_assets[ASSET_PIPE_WIDTH],
            udeks_vdc_text_assets[ASSET_PIPE_HEIGHT],
            pipe_map()) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return draw_tile_map(
        WORDMARK_X, WORDMARK_Y,
        udeks_vdc_text_assets[ASSET_WORD_WIDTH],
        udeks_vdc_text_assets[ASSET_WORD_HEIGHT],
        wordmark_map());
}

static unsigned char draw_frame(void)
{
    unsigned char column;
    unsigned char row;

    frame_buffer[0] = udeks_vdc_text_assets[ASSET_BORDER_TL];
    for (column = 1; column <= UDEKS_ROOT_CONSOLE_COLUMNS; ++column) {
        frame_buffer[column] = udeks_vdc_text_assets[ASSET_BORDER_H];
    }
    frame_buffer[UDEKS_ROOT_CONSOLE_COLUMNS + 1u] =
        udeks_vdc_text_assets[ASSET_BORDER_TR];
    if (vdc_write_block_at(
            (unsigned int)FRAME_TOP * SCREEN_WIDTH + FRAME_LEFT,
            frame_buffer, sizeof(frame_buffer)) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    for (row = UDEKS_CONSOLE_ROOT_Y; row < FRAME_BOTTOM; ++row) {
        frame_buffer[0] = udeks_vdc_text_assets[ASSET_BORDER_V];
        frame_buffer[1] = udeks_vdc_text_assets[ASSET_BORDER_V];
        if (vdc_write_block_at(
                (unsigned int)row * SCREEN_WIDTH + FRAME_LEFT,
                frame_buffer, 1u) != UDEKS_VDC_OK ||
            vdc_write_block_at(
                (unsigned int)row * SCREEN_WIDTH + FRAME_RIGHT,
                frame_buffer + 1u, 1u) != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
    }
    frame_buffer[0] = udeks_vdc_text_assets[ASSET_BORDER_BL];
    for (column = 1; column <= UDEKS_ROOT_CONSOLE_COLUMNS; ++column) {
        frame_buffer[column] = udeks_vdc_text_assets[ASSET_BORDER_H];
    }
    frame_buffer[UDEKS_ROOT_CONSOLE_COLUMNS + 1u] =
        udeks_vdc_text_assets[ASSET_BORDER_BR];
    return vdc_write_block_at(
        (unsigned int)FRAME_BOTTOM * SCREEN_WIDTH + FRAME_LEFT,
        frame_buffer, sizeof(frame_buffer));
}

static unsigned char update_hardware_cursor(void)
{
    unsigned int address;
    unsigned char start;

    address = (unsigned int)(
        UDEKS_CONSOLE_ROOT_Y + udeks_root_console_cursor_row()) *
        SCREEN_WIDTH + UDEKS_CONSOLE_ROOT_X +
        udeks_root_console_cursor_column();
    if (vdc_register_write(
            VDC_REG_CURSOR_HI, (unsigned char)(address >> 8)) != UDEKS_VDC_OK ||
        vdc_register_write(
            VDC_REG_CURSOR_LO, (unsigned char)address) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    start = udeks_root_console_cursor_visible() != 0 ? 0x00u : 0x20u;
    if (vdc_register_write(VDC_REG_CURSOR_START, start) != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_CURSOR_END, 7u) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return UDEKS_VDC_OK;
}

unsigned char udeks_console_refresh_root(void)
{
    const unsigned char *source;
    unsigned char row;
    unsigned char first;
    unsigned char last;
    unsigned char column;
    unsigned char length;

    for (row = 0; row < UDEKS_ROOT_CONSOLE_ROWS; ++row) {
        if (udeks_root_console_dirty_span(row, &first, &last) == 0) {
            continue;
        }
        source = udeks_root_console_row(row);
        length = (unsigned char)(last - first + 1u);
        for (column = 0; column < length; ++column) {
            row_buffer[column] = screen_code(source[first + column]);
            attribute_buffer[column] = (unsigned char)(
                SCREEN_ATTRIBUTE |
                (source[first + column] >= 'a' &&
                 source[first + column] <= 'z' ?
                    SCREEN_ATTRIBUTE_ALT : 0u));
        }
        if (vdc_write_block_at(
                (unsigned int)(UDEKS_CONSOLE_ROOT_Y + row) * SCREEN_WIDTH +
                    UDEKS_CONSOLE_ROOT_X + first,
                row_buffer, length) != UDEKS_VDC_OK ||
            vdc_write_block_at(
                ATTRIBUTE_BASE +
                    (unsigned int)(UDEKS_CONSOLE_ROOT_Y + row) * SCREEN_WIDTH +
                    UDEKS_CONSOLE_ROOT_X + first,
                attribute_buffer, length) != UDEKS_VDC_OK) {
            return UDEKS_CONSOLE_VDC_ERROR;
        }
        udeks_root_console_mark_row_clean(row);
    }
    if (update_hardware_cursor() != UDEKS_VDC_OK) {
        return UDEKS_CONSOLE_VDC_ERROR;
    }
    return UDEKS_CONSOLE_OK;
}

static unsigned char vdc_read_memory(void)
{
    if (vdc_begin_memory() != UDEKS_VDC_OK) {
        return 0;
    }
    return udeks_vdc_read_selected();
}

static unsigned char console_fail(unsigned char code)
{
    service_failure = code;
    STATUS_BYTE(6) = code;
    STATUS_BYTE(5) = (unsigned char)(UDEKS_CONSOLE_STATE_ERROR | code);
    return code;
}

unsigned char udeks_console_start(void)
{
    unsigned char value;
    unsigned int verify_address;

    status_begin();
    if (vdc_register_write(VDC_REG_DISPLAY_HI, 0x00) != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_DISPLAY_LO, 0x00) != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_ATTRIBUTE_HI, 0x08) != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_ATTRIBUTE_LO, 0x00) != UDEKS_VDC_OK) {
        return console_fail(1);
    }

    value = vdc_register_read(VDC_REG_HORIZONTAL_SCROLL);
    value = (unsigned char)((value & 0x7Fu) | 0x40u);
    if (udeks_vdc_status != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_HORIZONTAL_SCROLL, value) != UDEKS_VDC_OK) {
        return console_fail(2);
    }
    STATUS_BYTE(15) = value;
    if (vdc_register_write(VDC_REG_COLOR, UDEKS_THEME_VDC_COLOR) != UDEKS_VDC_OK) {
        return console_fail(3);
    }
    STATUS_BYTE(16) = UDEKS_THEME_VDC_COLOR;

    if (vdc_fill(SCREEN_BASE, 0x20, 2000u) != UDEKS_VDC_OK) {
        return console_fail(4);
    }
    if (vdc_fill(ATTRIBUTE_BASE, SCREEN_ATTRIBUTE, 2000u) != UDEKS_VDC_OK) {
        return console_fail(5);
    }
    if (upload_custom_glyphs() != UDEKS_VDC_OK) {
        return console_fail(6);
    }
    if (draw_logo() != UDEKS_VDC_OK || draw_frame() != UDEKS_VDC_OK) {
        return console_fail(7);
    }
    if (udeks_boot_console_build() != UDEKS_ROOT_CONSOLE_OK ||
        udeks_console_refresh_root() != UDEKS_CONSOLE_OK) {
        return console_fail(8);
    }

    verify_address = (unsigned int)UDEKS_CONSOLE_ROOT_Y * SCREEN_WIDTH +
        UDEKS_CONSOLE_ROOT_X;
    address_high = (unsigned char)(verify_address >> 8);
    address_low = (unsigned char)verify_address;
    STATUS_BYTE(12) = vdc_read_memory();
    if (udeks_vdc_status != UDEKS_VDC_OK || STATUS_BYTE(12) != 0x15u) {
        return console_fail(9);
    }
    verify_address += ATTRIBUTE_BASE;
    address_high = (unsigned char)(verify_address >> 8);
    address_low = (unsigned char)verify_address;
    STATUS_BYTE(13) = vdc_read_memory();
    if (udeks_vdc_status != UDEKS_VDC_OK ||
        STATUS_BYTE(13) != SCREEN_ATTRIBUTE) {
        return console_fail(10);
    }

    STATUS_BYTE(6) = 0;
    STATUS_BYTE(5) = UDEKS_CONSOLE_STATE_READY;
    return 0;
}
