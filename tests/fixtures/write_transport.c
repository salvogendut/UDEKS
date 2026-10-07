/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Fault-injectable private IEC contract, not a mock filesystem. */
#include <stdint.h>
#include <string.h>
#include "udeks/iec_slow.h"
uint8_t udeks_iec_filename[UDEKS_IEC_FILENAME_MAX], udeks_iec_filename_length;
uint8_t test_open_error, test_listen_error, test_close_error, test_unlisten_error;
uint8_t test_status_error, test_untalk_error, test_device;
uint16_t test_calls[8], test_values[2048], test_bytes, test_fail_at;
uint16_t test_status[64], test_status_size, test_status_pos;
/* Call indexes: prepare/listen/send/unlisten/status/read/untalk/close.
 * Finish has its own counter so terminal cleanup can be asserted. */
uint16_t test_finish_count;

void test_reset(void)
{
    memset(test_calls, 0, sizeof(test_calls));
    memset(udeks_iec_filename, 0x5a, sizeof(udeks_iec_filename));
    udeks_iec_filename_length = 0x5a;
    test_open_error = test_listen_error = test_close_error = test_unlisten_error = 0;
    test_status_error = test_untalk_error = test_device = 0;
    test_bytes = test_finish_count = 0; test_fail_at = 65535;
    test_status[0] = '0'; test_status[1] = '0'; test_status[2] = ',';
    test_status[3] = 256+13; test_status_size = 4;
}
uint8_t udeks_iec_prepare_file(uint8_t device)
{ ++test_calls[0]; test_device = device; return test_open_error; }
uint8_t udeks_iec_listen_file(void)
{ ++test_calls[1]; return test_listen_error; }
uint8_t udeks_iec_write_byte(uint16_t value)
{
    ++test_calls[2];
    if (test_bytes == test_fail_at || test_bytes == 2048u) return UDEKS_IEC_TIMEOUT;
    test_values[test_bytes++] = value; return 0;
}
uint8_t udeks_iec_unlisten(void)
{ ++test_calls[3]; return test_unlisten_error; }
uint8_t udeks_iec_open_status(void)
{ ++test_calls[4]; test_status_pos = 0; return test_status_error; }
uint16_t udeks_iec_read_byte(void)
{ ++test_calls[5]; return test_status_pos < test_status_size ? test_status[test_status_pos++] : 512u; }
uint8_t udeks_iec_untalk(void)
{ ++test_calls[6]; return test_untalk_error; }
uint8_t udeks_iec_close(void)
{ ++test_calls[7]; return test_close_error; }
void udeks_iec_finish(void) { ++test_finish_count; }
