/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/capability.h"
#include "udeks/time.h"

#ifdef UDEKS_TIME_MODULE
extern volatile unsigned char udeks_time_status[UDEKS_TIME_STATUS_SIZE];
#define STATUS_BYTE(offset) udeks_time_status[offset]
#else
#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_TIME_STATUS_BASE + (offset)))
#endif

#define CIA1_TOD_TENTHS   (*(volatile unsigned char *)0xDC08u)
#define CIA1_TOD_SECONDS  (*(volatile unsigned char *)0xDC09u)
#define CIA1_TOD_MINUTES  (*(volatile unsigned char *)0xDC0Au)
#define CIA1_TOD_HOURS    (*(volatile unsigned char *)0xDC0Bu)
#define CIA1_CRA          (*(volatile unsigned char *)0xDC0Eu)
#define CIA1_CRB          (*(volatile unsigned char *)0xDC0Fu)

void udeks_time_sync_ti(void);

#ifdef UDEKS_TIME_MODULE
/* Byte-valued lookup arithmetic avoids importing a 16-bit multiply routine
 * for these three samples. */
/* All three call sites mask away bit 7 before indexing. */
static const unsigned char bcd_tens[8] = {
    0, 10, 20, 30, 40, 50, 60, 70
};
static unsigned char bcd_to_binary(unsigned char value)
{
    return (unsigned char)(bcd_tens[value >> 4] + (value & 0x0fu));
}
#else
static unsigned char bcd_to_binary(unsigned char value)
{
    return (unsigned char)(((value >> 4) * 10u) + (value & 0x0Fu));
}
#endif

#ifdef UDEKS_TIME_MODULE
/* Both callers use fixed fields. Avoid an out-of-line variable-offset
 * counter (and its software-stack helpers) in the independently loaded
 * image; the existing exhaustive clock test checks the same semantics. */
#define increment_counter(low_offset) do { \
    if (++STATUS_BYTE(low_offset) == 0) { \
        ++STATUS_BYTE((low_offset) + 1u); \
    } \
} while (0)
#else
static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}
#endif

static unsigned char sample_tod(void)
{
    unsigned char raw_hour;
#ifndef UDEKS_TIME_MODULE
    unsigned char raw_minute;
    unsigned char raw_second;
#endif
    unsigned char raw_tenth;
    unsigned char hour;
    unsigned char minute;
    unsigned char second;

    /* Reading hours latches a coherent TOD value until tenths is read. */
    raw_hour = CIA1_TOD_HOURS;
#ifdef UDEKS_TIME_MODULE
    /* Conversion while TOD is latched is safe; tenths remains the last
     * hardware read, so no extra raw-byte copies are needed in this image. */
    minute = bcd_to_binary((unsigned char)(CIA1_TOD_MINUTES & 0x7fu));
    second = bcd_to_binary((unsigned char)(CIA1_TOD_SECONDS & 0x7fu));
    raw_tenth = CIA1_TOD_TENTHS;
    hour = bcd_to_binary((unsigned char)(raw_hour & 0x1fu));
#else
    raw_minute = CIA1_TOD_MINUTES;
    raw_second = CIA1_TOD_SECONDS;
    raw_tenth = CIA1_TOD_TENTHS;
    hour = bcd_to_binary((unsigned char)(raw_hour & 0x1Fu));
    minute = bcd_to_binary((unsigned char)(raw_minute & 0x7Fu));
    second = bcd_to_binary((unsigned char)(raw_second & 0x7Fu));
#endif
    if (hour > 12u || minute > 59u || second > 59u ||
        raw_tenth > 9u) {
        return UDEKS_TIME_INVALID;
    }
    if ((raw_hour & 0x80u) != 0) {
        hour = (unsigned char)(hour + 12u);
        if (hour == 24u) {
            hour = 12u;
        }
    } else if (hour == 12u) {
        hour = 0;
    }
    if (hour != STATUS_BYTE(8) || minute != STATUS_BYTE(9) ||
        second != STATUS_BYTE(10)) {
        increment_counter(18u);
    }
    STATUS_BYTE(8) = hour;
    STATUS_BYTE(9) = minute;
    STATUS_BYTE(10) = second;
    STATUS_BYTE(11) = raw_tenth;
    udeks_time_sync_ti();
    return UDEKS_TIME_OK;
}

unsigned char udeks_time_start(void)
{
    unsigned char offset;
    unsigned char control_b;
#ifndef UDEKS_TIME_MODULE
    unsigned char tenths;
#endif

#ifdef UDEKS_TIME_MODULE
    offset = UDEKS_TIME_STATUS_SIZE;
    do {
        --offset;
        STATUS_BYTE(offset) = 0;
    } while (offset != 0);
#else
    for (offset = 0; offset < UDEKS_TIME_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
#endif
    STATUS_BYTE(0) = 'T';
    STATUS_BYTE(1) = 'I';
    STATUS_BYTE(2) = 'M';
    STATUS_BYTE(3) = 'E';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_TIME_STARTING;
    STATUS_BYTE(7) = UDEKS_TIME_SOURCE_CIA1_TOD;
    /* Force the first coherent TOD sample to initialize BASIC's TI mirror. */
    STATUS_BYTE(12) = 0xFFu;
    if (*(volatile unsigned char *)(UDEKS_CAPABILITY_STATUS_BASE + 7u) ==
        UDEKS_VIDEO_PAL) {
        CIA1_CRA |= 0x80u;
    } else {
        CIA1_CRA &= 0x7Fu;
    }
    /* A tenths write starts a reset-stopped 6526 TOD without changing time. */
    control_b = CIA1_CRB;
    CIA1_CRB = (unsigned char)(control_b & 0x7Fu);
#ifdef UDEKS_TIME_MODULE
    CIA1_TOD_TENTHS &= 0x0fu;
#else
    tenths = CIA1_TOD_TENTHS;
    CIA1_TOD_TENTHS = (unsigned char)(tenths & 0x0Fu);
#endif
    CIA1_CRB = control_b;

    if (sample_tod() != UDEKS_TIME_OK) {
        STATUS_BYTE(5) = UDEKS_TIME_ERROR;
        return UDEKS_TIME_INVALID;
    }
    STATUS_BYTE(5) = UDEKS_TIME_READY;
    return UDEKS_TIME_OK;
}

unsigned char udeks_time_poll(void)
{
    if (STATUS_BYTE(5) != UDEKS_TIME_READY) {
        return UDEKS_TIME_INVALID;
    }
    increment_counter(16u);
    return sample_tod();
}

#ifndef UDEKS_TIME_MODULE
void udeks_time_now(
    unsigned char *hour, unsigned char *minute, unsigned char *second)
{
    *hour = STATUS_BYTE(8);
    *minute = STATUS_BYTE(9);
    *second = STATUS_BYTE(10);
}
#else
/* Lifecycle stop does not reset TOD or the scheduler's independent ticks.
 * The module manager must quiesce clients before invoking this entry. */
unsigned char udeks_time_stop(void)
{
    STATUS_BYTE(5) = 0;
    return 0;
}
#endif
