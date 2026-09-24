/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_MAILBOX_H
#define UDEKS_MAILBOX_H

/*
 * Provisional common-RAM mailbox ABI.
 *
 * This protocol is defined as byte offsets, not a C struct. cc65 and SDCC must
 * agree on bytes, not on compiler-specific packing or calling conventions.
 * Multi-byte values are little-endian.
 */

#define UDEKS_MAILBOX_BASE          0xF000u
#define UDEKS_MAILBOX_SIZE          64u

#define UDEKS_MB_MAGIC0             0u
#define UDEKS_MB_MAGIC1             1u
#define UDEKS_MB_MAGIC2             2u
#define UDEKS_MB_MAGIC3             3u
#define UDEKS_MB_ABI_MAJOR          4u
#define UDEKS_MB_ABI_MINOR          5u
#define UDEKS_MB_STATE              6u
#define UDEKS_MB_OPCODE             7u
#define UDEKS_MB_SEQUENCE_LO        8u
#define UDEKS_MB_SEQUENCE_HI        9u
#define UDEKS_MB_STATUS            10u
#define UDEKS_MB_FLAGS             11u
#define UDEKS_MB_ARG0_LO           12u
#define UDEKS_MB_ARG0_HI           13u
#define UDEKS_MB_ARG1_LO           14u
#define UDEKS_MB_ARG1_HI           15u
#define UDEKS_MB_LENGTH_LO         16u
#define UDEKS_MB_LENGTH_HI         17u
#define UDEKS_MB_RESULT_LO         18u
#define UDEKS_MB_RESULT_HI         19u

#define UDEKS_MAILBOX_ABI_MAJOR     0u
#define UDEKS_MAILBOX_ABI_MINOR     1u

#define UDEKS_MB_STATE_IDLE         0u
#define UDEKS_MB_STATE_SUBMITTED    1u
#define UDEKS_MB_STATE_RUNNING      2u
#define UDEKS_MB_STATE_COMPLETE     3u
#define UDEKS_MB_STATE_ERROR        0x80u

#define UDEKS_MB_OP_NOP             0u
#define UDEKS_MB_OP_COPY            1u
#define UDEKS_MB_OP_CHECKSUM16      2u
#define UDEKS_MB_OP_XOR_ROL         3u

#endif
