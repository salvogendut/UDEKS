/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/capability.h"
#include "udeks/vdc.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_CAPABILITY_STATUS_BASE + (offset)))

#define VDC_REG_UPDATE_HI       18u
#define VDC_REG_UPDATE_LO       19u
#define VDC_REG_MEMORY_CONFIG   28u
#define VDC_REG_DATA            31u

#define PROBE_COMPLETE_VIDEO    0x01u
#define PROBE_COMPLETE_REVISION 0x02u
#define PROBE_COMPLETE_VDC_RAM  0x04u
#define PROBE_COMPLETE_REU      0x08u
#define PROBE_COMPLETE_GEORAM   0x10u

#define CAPABILITY_ERROR_VIDEO  1u
#define CAPABILITY_ERROR_VDC    2u

static unsigned char probe_failure;

static unsigned char capability_fail(unsigned char code)
{
    probe_failure = code;
    STATUS_BYTE(6) = code;
    STATUS_BYTE(5) = (unsigned char)(UDEKS_CAPABILITY_STATE_ERROR | code);
    return code;
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

static unsigned char vdc_write_register(
    unsigned char reg, unsigned char value)
{
    if (udeks_vdc_select(reg) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return udeks_vdc_write_selected(value);
}

static unsigned char vdc_set_address(unsigned char high, unsigned char low)
{
    if (vdc_write_register(VDC_REG_UPDATE_HI, high) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return vdc_write_register(VDC_REG_UPDATE_LO, low);
}

static unsigned char vdc_memory_read(
    unsigned char high, unsigned char low, unsigned char *value)
{
    if (vdc_set_address(high, low) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return vdc_read_register(VDC_REG_DATA, value);
}

static unsigned char vdc_memory_write(
    unsigned char high, unsigned char low, unsigned char value)
{
    if (vdc_set_address(high, low) != UDEKS_VDC_OK ||
        udeks_vdc_select(VDC_REG_DATA) != UDEKS_VDC_OK) {
        return UDEKS_VDC_TIMEOUT;
    }
    return udeks_vdc_write_selected(value);
}

static unsigned char probe_vdc_ram(void)
{
    unsigned char original_low;
    unsigned char original_high;
    unsigned char low_result;
    unsigned char high_result;
    unsigned char saved_update_high;
    unsigned char saved_update_low;

    if (vdc_read_register(VDC_REG_UPDATE_HI, &saved_update_high) != UDEKS_VDC_OK ||
        vdc_read_register(VDC_REG_UPDATE_LO, &saved_update_low) != UDEKS_VDC_OK ||
        vdc_memory_read(0x1F, 0xFF, &original_low) != UDEKS_VDC_OK ||
        vdc_memory_read(0x9F, 0xFF, &original_high) != UDEKS_VDC_OK ||
        vdc_memory_write(0x1F, 0xFF, 0x55) != UDEKS_VDC_OK ||
        vdc_memory_write(0x9F, 0xFF, 0xAA) != UDEKS_VDC_OK ||
        vdc_memory_read(0x1F, 0xFF, &low_result) != UDEKS_VDC_OK ||
        vdc_memory_read(0x9F, 0xFF, &high_result) != UDEKS_VDC_OK) {
        return 0;
    }

    if (vdc_memory_write(0x9F, 0xFF, original_high) != UDEKS_VDC_OK ||
        vdc_memory_write(0x1F, 0xFF, original_low) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_UPDATE_HI, saved_update_high) != UDEKS_VDC_OK ||
        vdc_write_register(VDC_REG_UPDATE_LO, saved_update_low) != UDEKS_VDC_OK) {
        return 0;
    }

    if (low_result == 0x55 && high_result == 0xAA) {
        return 64;
    }
    if (low_result == 0xAA && high_result == 0xAA) {
        return 16;
    }
    return 0;
}

unsigned char udeks_capability_start(void)
{
    unsigned char offset;
    unsigned char video_standard;
    unsigned char vdc_revision;
    unsigned char vdc_family;
    unsigned char vdc_ram;
    unsigned char vdc_memory_config;
    unsigned char reu_present;
    unsigned char georam_present;
    unsigned char flags;

    for (offset = 0; offset < UDEKS_CAPABILITY_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'H';
    STATUS_BYTE(1) = 'C';
    STATUS_BYTE(2) = 'A';
    STATUS_BYTE(3) = 'P';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_CAPABILITY_STATE_PROBING;

    video_standard = udeks_probe_video_standard();
    if (video_standard == UDEKS_VIDEO_UNKNOWN) {
        return capability_fail(CAPABILITY_ERROR_VIDEO);
    }
    STATUS_BYTE(7) = video_standard;
    STATUS_BYTE(15) |= PROBE_COMPLETE_VIDEO;

    vdc_revision = udeks_probe_vdc_revision();
    if (vdc_revision == 0xFF) {
        return capability_fail(CAPABILITY_ERROR_VDC);
    }
    vdc_family = vdc_revision >= 2 ?
        UDEKS_VDC_FAMILY_8568 : UDEKS_VDC_FAMILY_8563;
    STATUS_BYTE(8) = vdc_revision;
    STATUS_BYTE(9) = vdc_family;
    STATUS_BYTE(14) = vdc_family == UDEKS_VDC_FAMILY_8568 ?
        UDEKS_MACHINE_HINT_DCR_8568 : UDEKS_MACHINE_HINT_C128_8563;
    STATUS_BYTE(15) |= PROBE_COMPLETE_REVISION;

    if (vdc_read_register(VDC_REG_MEMORY_CONFIG, &vdc_memory_config) !=
            UDEKS_VDC_OK) {
        return capability_fail(CAPABILITY_ERROR_VDC);
    }
    STATUS_BYTE(16) = vdc_memory_config;
    vdc_ram = probe_vdc_ram();
    if (vdc_ram == 0) {
        return capability_fail(CAPABILITY_ERROR_VDC);
    }
    STATUS_BYTE(10) = vdc_ram;
    STATUS_BYTE(15) |= PROBE_COMPLETE_VDC_RAM;

    reu_present = udeks_probe_reu();
    georam_present = udeks_probe_georam();
    STATUS_BYTE(12) = reu_present;
    STATUS_BYTE(13) = georam_present;
    STATUS_BYTE(15) |= PROBE_COMPLETE_REU | PROBE_COMPLETE_GEORAM;

    flags = video_standard == UDEKS_VIDEO_PAL ?
        UDEKS_CAP_VIDEO_PAL : UDEKS_CAP_VIDEO_NTSC;
    if (vdc_ram == 64) {
        flags |= UDEKS_CAP_VDC_64K;
    }
    if (reu_present != 0) {
        flags |= UDEKS_CAP_REU;
    }
    if (georam_present != 0) {
        flags |= UDEKS_CAP_GEORAM;
    }
    if (vdc_family == UDEKS_VDC_FAMILY_8568) {
        flags |= UDEKS_CAP_VDC_8568;
    }
    STATUS_BYTE(11) = flags;
    STATUS_BYTE(5) = UDEKS_CAPABILITY_STATE_READY;
    return 0;
}
