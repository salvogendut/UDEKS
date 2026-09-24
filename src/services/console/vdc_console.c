/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/console.h"
#include "udeks/vdc.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_CONSOLE_STATUS_BASE + (offset)))

#define VDC_REG_CURSOR_START       10u
#define VDC_REG_DISPLAY_HI         12u
#define VDC_REG_DISPLAY_LO         13u
#define VDC_REG_UPDATE_HI          18u
#define VDC_REG_UPDATE_LO          19u
#define VDC_REG_ATTRIBUTE_HI       20u
#define VDC_REG_ATTRIBUTE_LO       21u
#define VDC_REG_HORIZONTAL_SCROLL  25u
#define VDC_REG_COLOR              26u
#define VDC_REG_DATA               31u

#define SCREEN_ATTRIBUTE           0x0Fu
#define SCREEN_WIDTH               80u
#define SCREEN_HEIGHT              25u

static unsigned char address_high;
static unsigned char address_low;
static unsigned char service_failure;
static unsigned char index_byte;
static unsigned char page_count;
static unsigned char tail_count;

static const unsigned char title[] = "UDEKS";
static const unsigned char subtitle[] =
    "UNIFIED DUAL-ENGINE EXECUTIVE KERNEL SYSTEM";
static const unsigned char state_line[] = "NATIVE MICROKERNEL ONLINE";
static const unsigned char engines[] =
    "8502 EXECUTIVE  |  Z80 WORKER INSTALLED";

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
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_CONSOLE_STATE_STARTING;
    STATUS_BYTE(7) = SCREEN_WIDTH;
    STATUS_BYTE(8) = SCREEN_HEIGHT;
    STATUS_BYTE(9) = SCREEN_ATTRIBUTE;
    STATUS_BYTE(10) = 0x00;
    STATUS_BYTE(11) = 0x08;
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

static unsigned char vdc_fill_2000(unsigned char value)
{
    if (vdc_begin_memory() != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }

    page_count = 7;
    do {
        index_byte = 0;
        do {
            if (udeks_vdc_write_selected(value) != UDEKS_VDC_OK) {
                return UDEKS_VDC_TIMEOUT;
            }
            ++index_byte;
        } while (index_byte != 0);
        --page_count;
    } while (page_count != 0);

    tail_count = 208;
    do {
        if (udeks_vdc_write_selected(value) != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
        --tail_count;
    } while (tail_count != 0);
    return UDEKS_VDC_OK;
}

static unsigned char screen_code(unsigned char value)
{
    if (value >= 'A' && value <= 'Z') {
        return (unsigned char)(value - 'A' + 1);
    }
    if (value >= 'a' && value <= 'z') {
        return (unsigned char)(value - 'a' + 1);
    }
    return value;
}

static unsigned char vdc_write_literal(const unsigned char *text)
{
    index_byte = 0;
    while (text[index_byte] != 0) {
        if (udeks_vdc_write_selected(screen_code(text[index_byte])) != UDEKS_VDC_OK) {
            return UDEKS_VDC_TIMEOUT;
        }
        ++index_byte;
    }
    return UDEKS_VDC_OK;
}

static unsigned char write_banners(void)
{
    address_high = 0x02;
    address_low = 0xA5;
    if (vdc_begin_memory() != UDEKS_VDC_OK ||
        vdc_write_literal(title) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }

    address_high = 0x03;
    address_low = 0x32;
    if (vdc_begin_memory() != UDEKS_VDC_OK ||
        vdc_write_literal(subtitle) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }

    address_high = 0x04;
    address_low = 0x2B;
    if (vdc_begin_memory() != UDEKS_VDC_OK ||
        vdc_write_literal(state_line) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }

    address_high = 0x04;
    address_low = 0xC4;
    if (vdc_begin_memory() != UDEKS_VDC_OK ||
        vdc_write_literal(engines) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return UDEKS_VDC_OK;
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

    status_begin();

    if (vdc_register_write(VDC_REG_DISPLAY_HI, 0x00) != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_DISPLAY_LO, 0x00) != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_ATTRIBUTE_HI, 0x08) != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_ATTRIBUTE_LO, 0x00) != UDEKS_VDC_OK) {
        return console_fail(1);
    }

    value = vdc_register_read(VDC_REG_HORIZONTAL_SCROLL);
    if (udeks_vdc_status != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_HORIZONTAL_SCROLL,
                           (unsigned char)(value | 0x40)) != UDEKS_VDC_OK) {
        return console_fail(2);
    }
    STATUS_BYTE(15) = (unsigned char)(value | 0x40);

    if (vdc_register_write(VDC_REG_COLOR, 0xF0) != UDEKS_VDC_OK) {
        return console_fail(3);
    }
    STATUS_BYTE(16) = 0xF0;

    value = vdc_register_read(VDC_REG_CURSOR_START);
    if (udeks_vdc_status != UDEKS_VDC_OK ||
        vdc_register_write(VDC_REG_CURSOR_START,
                           (unsigned char)((value & 0x1F) | 0x20)) != UDEKS_VDC_OK) {
        return console_fail(4);
    }

    address_high = 0x00;
    address_low = 0x00;
    if (vdc_fill_2000(0x20) != UDEKS_VDC_OK) {
        return console_fail(5);
    }
    address_high = 0x08;
    address_low = 0x00;
    if (vdc_fill_2000(SCREEN_ATTRIBUTE) != UDEKS_VDC_OK) {
        return console_fail(6);
    }
    if (write_banners() != UDEKS_VDC_OK) {
        return console_fail(7);
    }

    address_high = 0x02;
    address_low = 0xA5;
    STATUS_BYTE(12) = vdc_read_memory();
    if (udeks_vdc_status != UDEKS_VDC_OK || STATUS_BYTE(12) != 0x15) {
        return console_fail(8);
    }
    address_high = 0x0A;
    address_low = 0xA5;
    STATUS_BYTE(13) = vdc_read_memory();
    if (udeks_vdc_status != UDEKS_VDC_OK ||
        STATUS_BYTE(13) != SCREEN_ATTRIBUTE) {
        return console_fail(9);
    }

    STATUS_BYTE(6) = 0;
    STATUS_BYTE(5) = UDEKS_CONSOLE_STATE_READY;
    return 0;
}
