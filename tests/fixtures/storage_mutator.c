/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Policy seam: capture only, NEVER mutates host or emulated media. */
#include <stdint.h>
#include <string.h>
#include "udeks/cbm_mutate.h"
uint16_t test_mutate_calls;
uint8_t test_mutate_error, test_mutate_unit, test_mutate_op, test_mutate_has_destination;
uint8_t test_mutate_source[16], test_mutate_destination[16];
uint8_t udeks_cbm_mutate_poll(void) { return test_mutate_error; }
uint16_t test_mutate_aborts;
void udeks_cbm_mutate_abort(void) { ++test_mutate_aborts; }
uint8_t udeks_cbm_mutate(uint8_t device, uint8_t operation,
                        const uint8_t *source, const uint8_t *destination)
{
    ++test_mutate_calls;
    test_mutate_unit = device; test_mutate_op = operation;
    memcpy(test_mutate_source, source, 16);
    test_mutate_has_destination = destination != 0;
    if (destination) memcpy(test_mutate_destination, destination, 16);
    return test_mutate_error;
}
