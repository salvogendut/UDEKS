/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_SERVICE_H
#define UDEKS_SERVICE_H

#define UDEKS_SERVICE_ABI_MAJOR          0u
#define UDEKS_SERVICE_ABI_MINOR          1u

#define UDEKS_SERVICE_DESCRIPTOR_SIZE    16u
#define UDEKS_SERVICE_MAGIC0             0u
#define UDEKS_SERVICE_MAGIC1             1u
#define UDEKS_SERVICE_MAGIC2             2u
#define UDEKS_SERVICE_MAGIC3             3u
#define UDEKS_SERVICE_ABI_MAJOR_OFFSET   4u
#define UDEKS_SERVICE_ABI_MINOR_OFFSET   5u
#define UDEKS_SERVICE_CLASS_OFFSET       6u
#define UDEKS_SERVICE_INSTANCE_OFFSET    7u
#define UDEKS_SERVICE_FLAGS_OFFSET       8u
#define UDEKS_SERVICE_SIZE_OFFSET        9u
#define UDEKS_SERVICE_START_LO           10u
#define UDEKS_SERVICE_START_HI           11u
#define UDEKS_SERVICE_POLL_LO            12u
#define UDEKS_SERVICE_POLL_HI            13u
#define UDEKS_SERVICE_STOP_LO            14u
#define UDEKS_SERVICE_STOP_HI            15u

#define UDEKS_SERVICE_CLASS_CONSOLE      1u
#define UDEKS_SERVICE_CLASS_CAPABILITY   2u
#define UDEKS_SERVICE_CLASS_DISPLAY      3u
#define UDEKS_SERVICE_CLASS_MACHINE      4u
#define UDEKS_SERVICE_CLASS_INPUT        5u

#define UDEKS_SERVICE_FLAG_RESIDENT      0x01u
#define UDEKS_SERVICE_FLAG_CRITICAL      0x02u

#define UDEKS_SERVICE_STATUS_BASE        0xF090u
#define UDEKS_SERVICE_STATUS_SIZE        24u
#define UDEKS_SERVICE_STATE_STARTING     1u
#define UDEKS_SERVICE_STATE_READY        2u
#define UDEKS_SERVICE_STATE_ERROR        0x80u

unsigned char udeks_service_start_all(void);
unsigned char udeks_service_poll_all(void);

#endif
