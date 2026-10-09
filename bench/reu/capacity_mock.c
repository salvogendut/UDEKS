/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Host test transport, never linked into the target. Each cell represents
 * offset $100 in an expansion bank, with hardware-style aliasing. */
#include "udeks/reu.h"
unsigned char udeks_reu_request[UDEKS_REU_REQUEST_SIZE];
extern unsigned char udeks_reu_probe_byte;
unsigned char mock_ram[16];
unsigned char mock_banks;
unsigned char mock_unbacked;
unsigned char mock_latch;
unsigned int mock_calls;
unsigned int mock_fail;
unsigned int mock_corrupt;
unsigned char mock_fail_after_write;
unsigned char mock_directions[128];

unsigned char udeks_reu_transfer(void)
{
    unsigned char bank;
    ++mock_calls;
    if (mock_calls <= 128) mock_directions[mock_calls-1] = udeks_reu_request[0];
    if (!mock_banks) return 19;
    if (udeks_reu_request[1] || udeks_reu_request[2] ||
        udeks_reu_request[3] != 0x50 || udeks_reu_request[4] ||
        udeks_reu_request[5] != 1 || udeks_reu_request[7] != 1 ||
        udeks_reu_request[8] || udeks_reu_request[0] > 1) return 22;
    if (mock_calls == mock_fail && !mock_fail_after_write) return 5;
    if (mock_unbacked && udeks_reu_request[6] >= mock_banks) {
        if (udeks_reu_request[0]) udeks_reu_probe_byte = mock_latch;
        else mock_latch = udeks_reu_probe_byte;
        return mock_calls == mock_fail ? 5 : 0;
    }
    bank = (unsigned char)(udeks_reu_request[6] % mock_banks);
    if (udeks_reu_request[0]) {
        udeks_reu_probe_byte = mock_ram[bank];
        mock_latch = 0x37; /* arbitrary prefetch beyond the owned probe byte */
        if (mock_calls == mock_corrupt) udeks_reu_probe_byte ^= 0x55;
    } else mock_latch = mock_ram[bank] = udeks_reu_probe_byte;
    return mock_calls == mock_fail ? 5 : 0;
}
