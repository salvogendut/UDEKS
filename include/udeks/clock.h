/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CLOCK_H
#define UDEKS_CLOCK_H

#define UDEKS_CLOCK_STATUS_BASE       0xF100u
#define UDEKS_CLOCK_STATUS_SIZE       16u

#define UDEKS_CLOCK_STATE_STARTING    1u
#define UDEKS_CLOCK_STATE_READY       2u
#define UDEKS_CLOCK_STATE_ERROR       0x80u

#define UDEKS_CLOCK_FLAG_VIC_BLANKED  0x01u
#define UDEKS_CLOCK_FLAG_FAST_READBACK 0x02u
#define UDEKS_CLOCK_FLAG_CAPABILITY_READY 0x04u

unsigned char udeks_clock_start(void);

#endif
