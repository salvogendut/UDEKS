/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mailbox.h"
#include "udeks/memory.h"
#include "udeks/panic.h"
#include "udeks/service.h"

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
    unsigned char service_result;

    mailbox_initialize();
    service_result = udeks_service_start_all();
    if (service_result != 0) {
        udeks_panic((unsigned char)(UDEKS_PANIC_SERVICE_START_BASE |
                                   service_result));
    }

    for (;;) {
        service_result = udeks_service_poll_all();
        if (service_result != 0) {
            udeks_panic((unsigned char)(UDEKS_PANIC_SERVICE_POLL_BASE |
                                       service_result));
        }
    }
}
