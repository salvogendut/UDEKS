/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mailbox.h"

#define MAILBOX_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_MAILBOX_BASE + (offset)))

void z80_main(void)
{
    /*
     * Deliberately do not attempt a CPU handoff yet. Phase 1 will replace this
     * halt loop after the MMU transition has an emulator-backed test.
     */
    MAILBOX_BYTE(UDEKS_MB_STATUS) = 0;
    for (;;) {
    }
}
