/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/reu_store.h"
unsigned char mock_ram[32770]; /* REU arena with two independent guard bytes */
unsigned int mock_calls, mock_fail;
unsigned char mock_partial;
unsigned int mock_address, mock_count;
unsigned char mock_direction;

uint8_t udeks_reu_store_io(uint8_t direction, uint16_t address,
                          uint8_t *bytes, uint16_t count)
{
    ++mock_calls;
    mock_address = address;
    mock_count = count;
    mock_direction = direction;
    if (direction > 1 || !count || count > 256 || address >= 32768u ||
        count > 32768u - address) return 22;
    if (mock_calls == mock_fail) {
        if (!mock_partial) return 5;
        count = (count + 1u) / 2u;
    }
    if (direction) memcpy(bytes, mock_ram + 1u + address, count);
    else memcpy(mock_ram + 1u + address, bytes, count);
    return mock_calls == mock_fail ? 5 : 0;
}
