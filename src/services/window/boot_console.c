/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/boot_console.h"
#include "udeks/capability.h"
#include "udeks/root_console.h"

#define STATUS_COLUMN 58u

static const unsigned char text_title[] =
    "UDEKS - UNIFIED DUAL ENGINE EXECUTIVE KERNEL SYSTEM";
static const unsigned char text_version[] = "V0.1.0  (C) 2026";
static const unsigned char text_hardware[] =
    "INITIALIZING SYSTEM HARDWARE ...";
static const unsigned char text_memory[] = "DETECTING MEMORY ...";
static const unsigned char text_base_ram[] = "BASE RAM : 128 KB";
static const unsigned char text_vdc_ram_16k[] = "VDC RAM : 16 KB";
static const unsigned char text_vdc_ram_64k[] = "VDC RAM : 64 KB";
static const unsigned char text_console[] = "INITIALIZING CONSOLE ...";
static const unsigned char text_video_pal_8563[] = "VIDEO : PAL / VDC 8563";
static const unsigned char text_video_pal_8568[] = "VIDEO : PAL / VDC 8568";
static const unsigned char text_video_ntsc_8563[] = "VIDEO : NTSC / VDC 8563";
static const unsigned char text_video_ntsc_8568[] = "VIDEO : NTSC / VDC 8568";
static const unsigned char text_reu_yes[] = "REU : PRESENT";
static const unsigned char text_reu_no[] = "REU : NOT PRESENT";
static const unsigned char text_georam_yes[] = "GEORAM : PRESENT";
static const unsigned char text_georam_no[] = "GEORAM : NOT PRESENT";
static const unsigned char text_8502[] = "8502 EXECUTIVE : NATIVE MODE";
static const unsigned char text_z80[] = "Z80 WORKER : STAGED";
static const unsigned char text_storage[] = "STORAGE SERVICES : DEFERRED";
static const unsigned char text_filesystem[] = "FILESYSTEM SERVICES : DEFERRED";
static const unsigned char text_ready[] = "SYSTEM READY.";
static const unsigned char text_welcome[] = "WELCOME TO UDEKS.";
static const unsigned char text_prompt[] = "UDEKS:~>";
static const unsigned char text_status_ok[] = "[ OK ]";
static const unsigned char text_status_deferred[] = "[ -- ]";

static unsigned char write_line(
    unsigned char row, const unsigned char *text)
{
    return udeks_root_console_write_at(0, row, text);
}

static unsigned char write_status_line(
    unsigned char row, const unsigned char *text,
    const unsigned char *status)
{
    if (write_line(row, text) != UDEKS_ROOT_CONSOLE_OK) {
        return UDEKS_ROOT_CONSOLE_BOUNDS;
    }
    return udeks_root_console_write_at(STATUS_COLUMN, row, status);
}

unsigned char udeks_boot_console_build(void)
{
    volatile unsigned char *capability;
    const unsigned char *video_text;

    capability = (volatile unsigned char *)UDEKS_CAPABILITY_STATUS_BASE;
    if (capability[7] == UDEKS_VIDEO_PAL) {
        video_text = capability[9] == UDEKS_VDC_FAMILY_8568 ?
            text_video_pal_8568 : text_video_pal_8563;
    } else {
        video_text = capability[9] == UDEKS_VDC_FAMILY_8568 ?
            text_video_ntsc_8568 : text_video_ntsc_8563;
    }

    udeks_root_console_reset();
    if (write_line(0, text_title) != UDEKS_ROOT_CONSOLE_OK ||
        write_line(1, text_version) != UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(3, text_hardware, text_status_ok) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(4, text_memory, text_status_ok) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(5, text_base_ram, text_status_ok) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(
            6, capability[10] == 64 ?
                text_vdc_ram_64k : text_vdc_ram_16k,
            text_status_ok) != UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(7, text_console, text_status_ok) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(8, video_text, text_status_ok) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(
            9, capability[12] != 0 ? text_reu_yes : text_reu_no,
            capability[12] != 0 ?
                text_status_ok : text_status_deferred) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(
            10, capability[13] != 0 ? text_georam_yes : text_georam_no,
            capability[13] != 0 ?
                text_status_ok : text_status_deferred) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(11, text_8502, text_status_ok) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(12, text_z80, text_status_deferred) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(13, text_storage, text_status_deferred) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_status_line(14, text_filesystem, text_status_deferred) !=
            UDEKS_ROOT_CONSOLE_OK ||
        write_line(16, text_ready) != UDEKS_ROOT_CONSOLE_OK ||
        write_line(18, text_welcome) != UDEKS_ROOT_CONSOLE_OK ||
        write_line(20, text_prompt) != UDEKS_ROOT_CONSOLE_OK ||
        udeks_root_console_set_cursor(9, 20, 1) !=
            UDEKS_ROOT_CONSOLE_OK) {
        return UDEKS_ROOT_CONSOLE_BOUNDS;
    }
    return UDEKS_ROOT_CONSOLE_OK;
}
