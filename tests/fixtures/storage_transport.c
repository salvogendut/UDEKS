/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
#include "udeks/iec_slow.h"
uint8_t udeks_storage_request[38];
uint8_t test_open_error, test_close_error, test_open_count, test_close_count;
uint8_t udeks_iec_filename[16], udeks_iec_filename_length;
uint8_t test_dos_error, test_status_bad, test_status_error, test_talk_error;
static uint8_t status_mode, status_position;
uint16_t test_stream[512], test_length, test_position;
uint8_t udeks_iec_open_directory(uint8_t device)
{
    (void)device;
    ++test_open_count;
    test_position = 0;
    status_mode = 0;
    return test_open_error;
}
uint8_t udeks_iec_prepare_file(uint8_t device) { return udeks_iec_open_directory(device); }
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
    if (status_mode) {
        if (test_status_bad) return 0x200;
        switch (status_position++) {
            case 0: return '0'+test_dos_error/10;
            case 1: return '0'+test_dos_error%10;
            case 2: return ',';
            default: return 0x10d;
        }
    }
    if (test_position == test_length) return UDEKS_IEC_TIMEOUT << 8;
    return test_stream[test_position++];
}
