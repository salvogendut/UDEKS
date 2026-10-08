/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Policy seam only. Real backend and wire transport have separate tests. */
#include <stdint.h>
#include "udeks/cbm_write.h"
#include "udeks/storage_write.h"

uint16_t test_caller = 1;
uint16_t test_create_calls, test_write_calls, test_writer_close_calls;
uint8_t test_create_error, test_write_error, test_writer_close_error;
uint8_t test_create_unit, test_create_length, test_create_name[16];
uint8_t test_create_type;
uint8_t test_write_count, test_write_data[24], test_write_prefix = 255;
uint8_t udeks_cbm_written, udeks_cbm_write_dos_error;

uint16_t udeks_storage_caller(void) { return test_caller; }

void test_writer_reset(void)
{
    test_caller = 1;
    test_create_calls = test_write_calls = test_writer_close_calls = 0;
    test_create_error = test_write_error = test_writer_close_error = 0;
    test_create_type = test_create_unit = test_create_length = test_write_count = 0;
    test_write_prefix = 255;
    udeks_cbm_written = 0;
}

uint8_t udeks_cbm_create(uint8_t device, const uint8_t *name, uint8_t length, uint8_t type)
{
    uint8_t i;
    ++test_create_calls;
    test_create_unit = device; test_create_length = length; test_create_type = type;
    for (i = 0; i < 16u; ++i) test_create_name[i] = i < length ? name[i] : 0xa0u;
    return test_create_error;
}

uint8_t udeks_cbm_write(const uint8_t *data, uint8_t count)
{
    uint8_t i;
    ++test_write_calls; test_write_count = count;
    for (i = 0; i < count && i < 24u; ++i) test_write_data[i] = data[i];
    udeks_cbm_written = test_write_prefix < count ? test_write_prefix : count;
    return test_write_error;
}

uint8_t udeks_cbm_write_close(void)
{
    ++test_writer_close_calls;
    return test_writer_close_error;
}
