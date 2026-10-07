/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
#include "udeks/iec_slow.h"
uint8_t udeks_storage_request[38];
uint8_t udeks_storage_cwd, udeks_storage_boot_source;
uint8_t test_open_error, test_close_error, test_open_count, test_close_count;
uint8_t udeks_iec_filename[UDEKS_IEC_FILENAME_MAX], udeks_iec_filename_length;
uint8_t test_dos_error, test_status_bad, test_status_error, test_talk_error;
uint8_t test_tracks[64], test_numbers[64], test_command_error;
uint8_t test_units[64], test_device;
uint16_t test_sectors[16384], test_fail_at, test_position;
static uint8_t status_mode, status_position, selected, missing;
#ifdef UDEKS_IEC_WRITE
static uint16_t buffer[256];
uint8_t test_fail_command, test_listen_error, test_send_error, test_unlisten_error;
uint8_t test_ignore_update, test_update_error;
uint16_t test_update_count, test_send_count, test_sent_value, test_pointer_count;
uint8_t udeks_iec_listen_file(void) { return test_listen_error; }
uint8_t udeks_iec_write_byte(uint16_t value)
{
    ++test_send_count; test_sent_value = value;
    if (test_send_error) return test_send_error;
    if (test_position >= 256) return UDEKS_IEC_BAD_STATE;
    buffer[test_position++] = value & 255u;
    return 0;
}
uint8_t udeks_iec_unlisten(void) { return test_unlisten_error; }
void udeks_iec_finish(void) {}
#endif
uint8_t udeks_iec_prepare_file(uint8_t device)
{
    test_device = device;
    ++test_open_count;
    status_mode = missing = 0;
    return test_open_error;
}
uint8_t udeks_iec_command(void)
{
    uint8_t track, sector;
#ifdef UDEKS_IEC_WRITE
    uint16_t i;
    if (udeks_iec_filename[0] == 'B') {
        ++test_pointer_count;
        if (test_fail_command == 2) return UDEKS_IEC_TIMEOUT;
        if (udeks_iec_filename_length != 7u || udeks_iec_filename[6] != '1') return UDEKS_IEC_BAD_STATE;
        test_position = 1;
        return 0;
    }
    if (test_fail_command == (udeks_iec_filename[1] == '1' ? 1 : 3)) return UDEKS_IEC_TIMEOUT;
#endif
    track = (udeks_iec_filename[7]-'0')*10 + udeks_iec_filename[8]-'0';
    sector = (udeks_iec_filename[10]-'0')*10 + udeks_iec_filename[11]-'0';
    for (selected = 0; selected < 64; ++selected)
        if ((!test_units[selected] || test_units[selected] == test_device) &&
            test_tracks[selected] == track && test_numbers[selected] == sector) break;
    missing = selected == 64;
    test_position = 0;
#ifdef UDEKS_IEC_WRITE
    if (!missing) {
        if (udeks_iec_filename[1] == '1') {
            for (i = 0; i < 256u; ++i) buffer[i] = test_sectors[(uint16_t)selected*256+i];
        } else {
            ++test_update_count;
            if (test_update_error) return test_update_error;
            if (!test_ignore_update)
                for (i = 0; i < 256u; ++i) test_sectors[(uint16_t)selected*256+i] = buffer[i];
        }
    }
#endif
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
#ifdef UDEKS_IEC_WRITE
    result = buffer[test_position++];
#else
    result = test_sectors[(uint16_t)selected*256+test_position++];
#endif
    return test_position == 256 ? result | 0x100 : result;
}
