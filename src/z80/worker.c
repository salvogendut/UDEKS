/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mailbox.h"

#define MAILBOX_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_MAILBOX_BASE + (offset)))

extern void udeks_z80_yield(void);

static unsigned char validate_request(void)
{
    unsigned char offset;

    if (MAILBOX_BYTE(UDEKS_MB_MAGIC0) != 'U' ||
        MAILBOX_BYTE(UDEKS_MB_MAGIC1) != 'D' ||
        MAILBOX_BYTE(UDEKS_MB_MAGIC2) != 'E' ||
        MAILBOX_BYTE(UDEKS_MB_MAGIC3) != 'K') {
        return UDEKS_MB_STATUS_MAGIC;
    }
    if (MAILBOX_BYTE(UDEKS_MB_ABI_MAJOR) != UDEKS_MAILBOX_ABI_MAJOR ||
        MAILBOX_BYTE(UDEKS_MB_ABI_MINOR) > UDEKS_MAILBOX_ABI_MINOR) {
        return UDEKS_MB_STATUS_ABI;
    }
    if (MAILBOX_BYTE(UDEKS_MB_STATE) != UDEKS_MB_STATE_SUBMITTED) {
        return UDEKS_MB_STATUS_STATE;
    }
    if (MAILBOX_BYTE(UDEKS_MB_OPCODE) != UDEKS_MB_OP_NOP) {
        return UDEKS_MB_STATUS_OPCODE;
    }
    for (offset = 20u; offset < UDEKS_MAILBOX_SIZE; ++offset) {
        if (MAILBOX_BYTE(offset) != 0) {
            return UDEKS_MB_STATUS_RESERVED;
        }
    }
    return UDEKS_MB_STATUS_OK;
}

void z80_main(void)
{
    unsigned char status;

    for (;;) {
        status = validate_request();
        if (status == UDEKS_MB_STATUS_OK) {
            MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_RUNNING;
            MAILBOX_BYTE(UDEKS_MB_RESULT_LO) = 0;
            MAILBOX_BYTE(UDEKS_MB_RESULT_HI) = 0;
            MAILBOX_BYTE(UDEKS_MB_STATUS) = UDEKS_MB_STATUS_OK;
            MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_COMPLETE;
        } else {
            MAILBOX_BYTE(UDEKS_MB_STATUS) = status;
            MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_ERROR;
        }
        udeks_z80_yield();
    }
}
