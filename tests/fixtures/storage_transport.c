/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
#include "udeks/iec_slow.h"
uint8_t udeks_storage_request[38];
uint8_t test_open_error, test_close_error, test_open_count, test_close_count;
uint8_t udeks_iec_filename[16], udeks_iec_filename_length;
uint8_t test_dos_error, test_status_bad, test_status_error, test_talk_error;
uint8_t test_tracks[32], test_numbers[32], test_command_error;
uint16_t test_sectors[8192], test_fail_at, test_position;
static uint8_t status_mode, status_position, selected, missing;
uint8_t udeks_iec_prepare_file(uint8_t device)
{
    (void)device;
    ++test_open_count;
    status_mode = missing = 0;
    return test_open_error;
}
uint8_t udeks_iec_command(void)
{
    uint8_t track, sector;
    track = (udeks_iec_filename[7]-'0')*10 + udeks_iec_filename[8]-'0';
    sector = (udeks_iec_filename[10]-'0')*10 + udeks_iec_filename[11]-'0';
    for (selected = 0; selected < 32; ++selected)
        if (test_tracks[selected] == track && test_numbers[selected] == sector) break;
    missing = selected == 32;
    test_position = 0;
    return test_command_error;
}
uint8_t udeks_iec_open_status(void)
{
    status_mode = 1; status_position = 0;
    return test_status_error;
}
uint8_t udeks_iec_talk_file(void) { status_mode = 0; return test_talk_error; }
uint8_t udeks_iec_untalk(void) { status_mode = 0; return 0; }
uint8_t udeks_iec_close(void)
{
    ++test_close_count;
    return test_close_error;
}
uint16_t udeks_iec_read_byte(void)
{
    uint8_t error = missing ? 66 : test_dos_error;
    uint16_t result;
    if (status_mode) {
        if (test_status_bad) return 0x200;
        switch (status_position++) {
            case 0: return '0'+error/10;
            case 1: return '0'+error%10;
            case 2: return ',';
            default: return 0x10d;
        }
    }
    if (missing || test_position >= 256 || test_position == test_fail_at) return 0x200;
    result = test_sectors[(uint16_t)selected*256+test_position++];
    return test_position == 256 ? result | 0x100 : result;
}
