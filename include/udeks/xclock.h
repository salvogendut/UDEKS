/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_XCLOCK_H
#define UDEKS_XCLOCK_H

#define UDEKS_XCLOCK_STATUS_BASE       0xF220u
#define UDEKS_XCLOCK_STATUS_SIZE       32u

#define UDEKS_XCLOCK_READY             2u
#define UDEKS_XCLOCK_RUNNING           3u
#define UDEKS_XCLOCK_ERROR             0x80u

#define UDEKS_XCLOCK_OK                0u
#define UDEKS_XCLOCK_NOT_READY         1u
#define UDEKS_XCLOCK_ALREADY_RUNNING   2u

unsigned char udeks_xclock_initialize(void);
unsigned char udeks_xclock_start(void);
unsigned char udeks_xclock_poll(void);
unsigned char udeks_xclock_stop(void);
unsigned char udeks_xclock_is_running(void);

#endif
