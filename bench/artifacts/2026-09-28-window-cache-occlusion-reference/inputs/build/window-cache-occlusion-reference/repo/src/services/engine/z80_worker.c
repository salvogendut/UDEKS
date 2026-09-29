/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mailbox.h"
#include "udeks/memory.h"
#include "udeks/vic_graphics.h"
#include "udeks/z80_worker.h"

#define MAILBOX_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_MAILBOX_BASE + (offset)))
#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_Z80_WORKER_STATUS_BASE + (offset)))
#define BOOT_CHAIN_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_BOOT_CHAIN_BASE + (offset)))

#define STATUS_ERROR                 6u
#define STATUS_LAST_OPCODE           7u
#define STATUS_SEQUENCE_LO           8u
#define STATUS_SEQUENCE_HI           9u
#define STATUS_MAILBOX_STATUS       10u
#define STATUS_SELF_TEST            11u
#define STATUS_TRANSACTIONS_LO      12u
#define STATUS_FAILURES_LO          14u
#define STATUS_ABI_MAJOR            16u
#define STATUS_ABI_MINOR            17u
#define STATUS_IMAGE_STAGED         18u
#define STATUS_BOOTSTRAP_INSTALLED  19u
#define STATUS_TIMING_POLICY        20u
#define STATUS_LAST_STATE           21u

extern void udeks_z80_prepare(void);
extern void udeks_z80_handoff(void);

static unsigned int sequence;

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static void set_error(unsigned char error)
{
    STATUS_BYTE(STATUS_ERROR) = error;
    STATUS_BYTE(5) = UDEKS_Z80_WORKER_ERROR;
    increment_counter(STATUS_FAILURES_LO);
}

static unsigned char image_is_staged(void)
{
    return BOOT_CHAIN_BYTE(0) == 'S' &&
        BOOT_CHAIN_BYTE(1) == '0' &&
        BOOT_CHAIN_BYTE(2) == 'O' &&
        BOOT_CHAIN_BYTE(3) == 'K' &&
        BOOT_CHAIN_BYTE(4) == 'S' &&
        BOOT_CHAIN_BYTE(5) == '1' &&
        BOOT_CHAIN_BYTE(6) == 'O' &&
        BOOT_CHAIN_BYTE(7) == 'K' &&
        BOOT_CHAIN_BYTE(8) == 'Z' &&
        BOOT_CHAIN_BYTE(9) == '8' &&
        BOOT_CHAIN_BYTE(10) == '0' &&
        BOOT_CHAIN_BYTE(11) == '!' &&
        BOOT_CHAIN_BYTE(12) == 2u &&
        BOOT_CHAIN_BYTE(13) == 0u;
}

static unsigned char mailbox_header_is_valid(void)
{
    return MAILBOX_BYTE(UDEKS_MB_MAGIC0) == 'U' &&
        MAILBOX_BYTE(UDEKS_MB_MAGIC1) == 'D' &&
        MAILBOX_BYTE(UDEKS_MB_MAGIC2) == 'E' &&
        MAILBOX_BYTE(UDEKS_MB_MAGIC3) == 'K' &&
        MAILBOX_BYTE(UDEKS_MB_ABI_MAJOR) == UDEKS_MAILBOX_ABI_MAJOR &&
        MAILBOX_BYTE(UDEKS_MB_ABI_MINOR) <= UDEKS_MAILBOX_ABI_MINOR;
}

unsigned char udeks_z80_submit(
    unsigned char opcode, unsigned int argument0,
    unsigned int argument1, unsigned int length,
    unsigned int *result)
{
    unsigned char offset;

    if (STATUS_BYTE(5) != UDEKS_Z80_WORKER_STARTING &&
        STATUS_BYTE(5) != UDEKS_Z80_WORKER_READY) {
        return UDEKS_Z80_NOT_READY;
    }
    if (!mailbox_header_is_valid()) {
        set_error(UDEKS_Z80_MAILBOX_INVALID);
        return UDEKS_Z80_MAILBOX_INVALID;
    }

    ++sequence;
    for (offset = UDEKS_MB_STATUS; offset < UDEKS_MAILBOX_SIZE; ++offset) {
        MAILBOX_BYTE(offset) = 0;
    }
    MAILBOX_BYTE(UDEKS_MB_OPCODE) = opcode;
    MAILBOX_BYTE(UDEKS_MB_SEQUENCE_LO) = (unsigned char)sequence;
    MAILBOX_BYTE(UDEKS_MB_SEQUENCE_HI) = (unsigned char)(sequence >> 8);
    MAILBOX_BYTE(UDEKS_MB_ARG0_LO) = (unsigned char)argument0;
    MAILBOX_BYTE(UDEKS_MB_ARG0_HI) = (unsigned char)(argument0 >> 8);
    MAILBOX_BYTE(UDEKS_MB_ARG1_LO) = (unsigned char)argument1;
    MAILBOX_BYTE(UDEKS_MB_ARG1_HI) = (unsigned char)(argument1 >> 8);
    MAILBOX_BYTE(UDEKS_MB_LENGTH_LO) = (unsigned char)length;
    MAILBOX_BYTE(UDEKS_MB_LENGTH_HI) = (unsigned char)(length >> 8);
    MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_SUBMITTED;

    STATUS_BYTE(STATUS_LAST_OPCODE) = opcode;
    STATUS_BYTE(STATUS_SEQUENCE_LO) = (unsigned char)sequence;
    STATUS_BYTE(STATUS_SEQUENCE_HI) = (unsigned char)(sequence >> 8);
    udeks_vic_pointer_busy_begin(UDEKS_VIC_BUSY_Z80);
    udeks_z80_handoff();
    udeks_vic_pointer_busy_end(UDEKS_VIC_BUSY_Z80);
    STATUS_BYTE(STATUS_LAST_STATE) = MAILBOX_BYTE(UDEKS_MB_STATE);
    STATUS_BYTE(STATUS_MAILBOX_STATUS) = MAILBOX_BYTE(UDEKS_MB_STATUS);

    if (MAILBOX_BYTE(UDEKS_MB_SEQUENCE_LO) != (unsigned char)sequence ||
        MAILBOX_BYTE(UDEKS_MB_SEQUENCE_HI) !=
            (unsigned char)(sequence >> 8)) {
        set_error(UDEKS_Z80_SEQUENCE_INVALID);
        return UDEKS_Z80_SEQUENCE_INVALID;
    }
    if (MAILBOX_BYTE(UDEKS_MB_STATE) == UDEKS_MB_STATE_ERROR ||
        MAILBOX_BYTE(UDEKS_MB_STATUS) != UDEKS_MB_STATUS_OK) {
        increment_counter(STATUS_FAILURES_LO);
        return UDEKS_Z80_WORKER_REJECTED;
    }
    if (MAILBOX_BYTE(UDEKS_MB_STATE) != UDEKS_MB_STATE_COMPLETE) {
        set_error(UDEKS_Z80_RESPONSE_INVALID);
        return UDEKS_Z80_RESPONSE_INVALID;
    }
    if (result != 0) {
        *result = (unsigned int)MAILBOX_BYTE(UDEKS_MB_RESULT_LO) |
            ((unsigned int)MAILBOX_BYTE(UDEKS_MB_RESULT_HI) << 8);
    }
    increment_counter(STATUS_TRANSACTIONS_LO);
    return UDEKS_Z80_OK;
}

unsigned char udeks_z80_worker_start(void)
{
    unsigned char offset;
    unsigned char result;
    unsigned int worker_result;

    for (offset = 0; offset < UDEKS_Z80_WORKER_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'Z';
    STATUS_BYTE(1) = 'W';
    STATUS_BYTE(2) = 'R';
    STATUS_BYTE(3) = 'K';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_Z80_WORKER_OFFLINE;
    STATUS_BYTE(STATUS_ABI_MAJOR) = UDEKS_MAILBOX_ABI_MAJOR;
    STATUS_BYTE(STATUS_ABI_MINOR) = UDEKS_MAILBOX_ABI_MINOR;
    STATUS_BYTE(STATUS_TIMING_POLICY) = UDEKS_Z80_TIMING_STOCK;

    if (!image_is_staged()) {
        STATUS_BYTE(STATUS_ERROR) = UDEKS_Z80_NOT_STAGED;
        return UDEKS_Z80_OK;
    }
    STATUS_BYTE(STATUS_IMAGE_STAGED) = 1;
    STATUS_BYTE(5) = UDEKS_Z80_WORKER_STARTING;
    udeks_z80_prepare();
    STATUS_BYTE(STATUS_BOOTSTRAP_INSTALLED) = 1;
    result = udeks_z80_submit(
        UDEKS_MB_OP_NOP, 0, 0, 0, &worker_result);
    STATUS_BYTE(STATUS_SELF_TEST) = result;
    if (result != UDEKS_Z80_OK || worker_result != 0) {
        if (STATUS_BYTE(5) != UDEKS_Z80_WORKER_ERROR) {
            set_error(result != UDEKS_Z80_OK ? result :
                UDEKS_Z80_RESPONSE_INVALID);
        }
        return UDEKS_Z80_OK;
    }
    STATUS_BYTE(5) = UDEKS_Z80_WORKER_READY;
    return UDEKS_Z80_OK;
}
