/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_XWAVE_H
#define UDEKS_XWAVE_H

#define UDEKS_XWAVE_STATUS_BASE       0xF260u
#define UDEKS_XWAVE_STATUS_SIZE       32u

#define UDEKS_XWAVE_READY             2u
#define UDEKS_XWAVE_RUNNING           3u

#define UDEKS_XWAVE_OK                0u
#define UDEKS_XWAVE_NOT_READY         1u
#define UDEKS_XWAVE_ALREADY_RUNNING   2u

unsigned char udeks_xwave_initialize(void);
unsigned char udeks_xwave_start(void);
unsigned char udeks_xwave_poll(void);
unsigned char udeks_xwave_stop(void);
unsigned char udeks_xwave_is_running(void);
unsigned char udeks_xwave_is_focused(void);

#endif
