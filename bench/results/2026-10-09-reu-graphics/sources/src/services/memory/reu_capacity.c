/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/reu.h"

unsigned char udeks_reu_capacity_banks;
/* The hardware transport needs a physical bank-0 address. This buffer and
 * this C module must eventually have a verified service-owned placement. */
unsigned char udeks_reu_probe_byte;
static unsigned char original[8];

static unsigned char transfer(unsigned char bank)
{
    udeks_reu_request[UDEKS_REU_BANK] = bank;
    return udeks_reu_transfer();
}

unsigned char udeks_reu_discover(void)
{
    unsigned char bank;
    unsigned char banks = 0;
    unsigned char error = 0;
    unsigned char status;
    unsigned char tag_base = 0;
    unsigned char unbacked = 0;
    unsigned int address;

    udeks_reu_capacity_banks = 0;
#ifdef UDEKS_REU_HOST_TEST
    address = 0x5000u; /* mock transport reads/writes probe_byte */
#else
    address = (unsigned int)&udeks_reu_probe_byte;
#endif
    for (bank = 0; bank != UDEKS_REU_REQUEST_SIZE; ++bank)
        udeks_reu_request[bank] = 0;
    udeks_reu_request[UDEKS_REU_HOST_LO] = (unsigned char)address;
    udeks_reu_request[UDEKS_REU_HOST_HI] = (unsigned char)(address >> 8);
    udeks_reu_request[UDEKS_REU_ADDRESS_HI] = 1;
    udeks_reu_request[UDEKS_REU_COUNT_LO] = 1;
    udeks_reu_request[UDEKS_REU_DIRECTION] = UDEKS_REU_FETCH;
    /* Save ALL aliases before the first mutation. */
    for (bank = 0; bank != 8; ++bank) {
        status = transfer(bank);
        if (status) return status;
        original[bank] = udeks_reu_probe_byte;
    }
    udeks_reu_request[UDEKS_REU_DIRECTION] = UDEKS_REU_STASH;
    for (bank = 0; bank != 8; ++bank) {
        udeks_reu_probe_byte = (unsigned char)(0xa0u + bank);
        status = transfer(bank);
        if (status) { error = status; break; }
    }
    udeks_reu_request[UDEKS_REU_DIRECTION] = UDEKS_REU_FETCH;
    if (!error) {
        error = transfer(0);
        if (!error) {
            tag_base = udeks_reu_probe_byte;
            if (udeks_reu_probe_byte == 0xa6u) banks = 2;
            else if (udeks_reu_probe_byte == 0xa4u) banks = 4;
            else if (udeks_reu_probe_byte == 0xa0u) banks = 8;
            else error = 5; /* EIO: unsupported alias geometry */
        }
    }
    if (!error) {
        for (bank = 0; bank != 8; ++bank) {
            /* Prime the REC bus with a DIFFERENT known byte. Empty sockets
             * can echo its last latched value, not necessarily $FF. Only the
             * non-mirrored eight-bank candidate needs this check. */
            if (banks == 8 && bank) {
                udeks_reu_request[UDEKS_REU_DIRECTION] = UDEKS_REU_STASH;
                udeks_reu_probe_byte = 0xa0u;
                status = transfer(0);
                udeks_reu_request[UDEKS_REU_DIRECTION] = UDEKS_REU_FETCH;
                if (status) { error = status; break; }
            }
            status = transfer(bank);
            if (status) { error = status; break; }
            /* A 1764's upper four banks are unpopulated, not mirrors. We
             * have independently proved the first four; claim only those.
             * Also accept genuine four-bank mirroring (tag_base == $A4). */
            if (banks == 8 && bank == 4 && udeks_reu_probe_byte == 0xa0u) {
                banks = 4;
                unbacked = 1;
                break;
            }
            if (udeks_reu_probe_byte !=
                    (unsigned char)(tag_base + (bank & (banks - 1u)))) {
                error = 5;
                break;
            }
        }
    }
    /* Restore all preimages even after a failed/partial write. A broken
     * device cannot promise restoration; any such error keeps capacity zero. */
    udeks_reu_request[UDEKS_REU_DIRECTION] = UDEKS_REU_STASH;
    for (bank = 0; bank != 8; ++bank) {
        udeks_reu_probe_byte = original[bank];
        status = transfer(bank);
        if (status) error = status;
    }
    udeks_reu_request[UDEKS_REU_DIRECTION] = UDEKS_REU_FETCH;
    /* Unpopulated sockets have no contents to verify; their bus latch may
     * legitimately differ from the initial read. */
    for (bank = 0; bank != (unbacked ? 4 : 8); ++bank) {
        status = transfer(bank);
        if (status) error = status;
        else if (udeks_reu_probe_byte != original[bank]) error = 5;
    }
    if (!error) udeks_reu_capacity_banks = banks;
    return error;
}
