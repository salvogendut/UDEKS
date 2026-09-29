/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_Z80_WORKER_H
#define UDEKS_Z80_WORKER_H

#define UDEKS_Z80_WORKER_STATUS_BASE       0xF190u
#define UDEKS_Z80_WORKER_STATUS_SIZE       32u

#define UDEKS_Z80_WORKER_OFFLINE           0u
#define UDEKS_Z80_WORKER_STARTING          1u
#define UDEKS_Z80_WORKER_READY             2u
#define UDEKS_Z80_WORKER_ERROR             0x80u

#define UDEKS_Z80_OK                       0u
#define UDEKS_Z80_NOT_STAGED               1u
#define UDEKS_Z80_NOT_READY                2u
#define UDEKS_Z80_MAILBOX_INVALID          3u
#define UDEKS_Z80_RESPONSE_INVALID         4u
#define UDEKS_Z80_SEQUENCE_INVALID         5u
#define UDEKS_Z80_WORKER_REJECTED          6u

#define UDEKS_Z80_TIMING_STOCK             1u

unsigned char udeks_z80_worker_start(void);
unsigned char udeks_z80_submit(
    unsigned char opcode, unsigned int argument0,
    unsigned int argument1, unsigned int length,
    unsigned int *result);

#endif
