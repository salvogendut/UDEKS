/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
#include <string.h>
#include "udeks/iec_slow.h"
uint8_t udeks_iec_filename[UDEKS_IEC_FILENAME_MAX], udeks_iec_filename_length;
uint8_t test_begin_error, test_command_error, test_status_error, test_untalk_error;
uint8_t test_device;
uint16_t test_calls[7], test_status[80], test_size, test_pos;
void test_reset(void)
{
    memset(test_calls, 0, sizeof(test_calls));
    memset(udeks_iec_filename, 0x5a, sizeof(udeks_iec_filename));
    udeks_iec_filename_length = 0x5a;
    test_begin_error = test_command_error = test_status_error = test_untalk_error = 0;
    test_device = test_size = test_pos = 0;
}
uint8_t udeks_iec_begin_command(uint8_t device)
{ ++test_calls[0]; test_device = device; return test_begin_error; }
uint8_t udeks_iec_command(void) { ++test_calls[1]; return test_command_error; }
uint8_t udeks_iec_open_status(void) { ++test_calls[2]; test_pos = 0; return test_status_error; }
uint16_t udeks_iec_read_byte(void)
{ ++test_calls[3]; return test_pos < test_size ? test_status[test_pos++] : 512u; }
uint8_t udeks_iec_untalk(void) { ++test_calls[4]; return test_untalk_error; }
void udeks_iec_finish(void) { ++test_calls[5]; }
uint8_t udeks_iec_unlisten(void) { ++test_calls[6]; return 0; }
