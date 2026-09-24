/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TIME_H
#define UDEKS_TIME_H

#define UDEKS_TIME_STATUS_BASE       0xF200u
#define UDEKS_TIME_STATUS_SIZE       24u

#define UDEKS_TIME_STARTING          1u
#define UDEKS_TIME_READY             2u
#define UDEKS_TIME_ERROR             0x80u

#define UDEKS_TIME_OK                0u
#define UDEKS_TIME_INVALID           1u

#define UDEKS_TIME_SOURCE_CIA1_TOD   1u

unsigned char udeks_time_start(void);
unsigned char udeks_time_poll(void);
void udeks_time_now(
    unsigned char *hour, unsigned char *minute, unsigned char *second);

#endif
