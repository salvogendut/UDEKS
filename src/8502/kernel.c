/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mailbox.h"

#define MAILBOX_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_MAILBOX_BASE + (offset)))

static void mailbox_initialize(void)
{
    MAILBOX_BYTE(UDEKS_MB_MAGIC0) = 'U';
    MAILBOX_BYTE(UDEKS_MB_MAGIC1) = 'D';
    MAILBOX_BYTE(UDEKS_MB_MAGIC2) = 'E';
    MAILBOX_BYTE(UDEKS_MB_MAGIC3) = 'K';
    MAILBOX_BYTE(UDEKS_MB_ABI_MAJOR) = UDEKS_MAILBOX_ABI_MAJOR;
    MAILBOX_BYTE(UDEKS_MB_ABI_MINOR) = UDEKS_MAILBOX_ABI_MINOR;
    MAILBOX_BYTE(UDEKS_MB_OPCODE) = UDEKS_MB_OP_NOP;
    MAILBOX_BYTE(UDEKS_MB_STATUS) = 0;
    MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_IDLE;
}

void kernel_main(void)
{
    mailbox_initialize();

    /* Bring-up halt. Scheduler and interrupt enablement come in Phase 2. */
    for (;;) {
    }
}
