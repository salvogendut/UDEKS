/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Compatibility snapshot marshalling only. No TOD access or clock policy.
 * This preserves the published UAPP C calling convention. That old void
 * interface has no errno channel; clients must check TIME's READY byte.
 */
#include "udeks/time.h"
#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_TIME_STATUS_BASE + (offset)))

void udeks_time_now(
    unsigned char *hour, unsigned char *minute, unsigned char *second)
{
    *hour = STATUS_BYTE(8);
    *minute = STATUS_BYTE(9);
    *second = STATUS_BYTE(10);
}
