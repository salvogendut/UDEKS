/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_REU_H
#define UDEKS_REU_H

/* PRIVATE candidate transport, not a task ABI and not yet installed in boot.
 * Serialized calls from the 8502 kernel-IO profile only. Caller must own the
 * host range and have checked expansion capacity/ownership. No simultaneous
 * REU user or armed DMA is allowed. RAM expansion is optional.
 * Byte layout avoids host/cc65 structure packing differences. */
#define UDEKS_REU_STASH       0u
#define UDEKS_REU_FETCH       1u
#define UDEKS_REU_DIRECTION   0u
#define UDEKS_REU_HOST_BANK   1u
#define UDEKS_REU_HOST_LO     2u
#define UDEKS_REU_HOST_HI     3u
#define UDEKS_REU_ADDRESS_LO  4u
#define UDEKS_REU_ADDRESS_HI  5u
#define UDEKS_REU_BANK       6u
#define UDEKS_REU_COUNT_LO   7u
#define UDEKS_REU_COUNT_HI   8u
#define UDEKS_REU_REQUEST_SIZE 9u
#define UDEKS_REU_CHUNK_MAX   256u

extern unsigned char udeks_reu_request[UDEKS_REU_REQUEST_SIZE];
/* 0, EIO=5, ENODEV=19, EINVAL=22. Preserves processor I/D, MMU CR/RCR, speed.
 * The REC register block is owned by this driver, not saved/restored. */
unsigned char udeks_reu_transfer(void);

/* Conservative discovery of the first 128/256/512 KiB. Larger REUs expose a
 * verified 512 KiB prefix for now, NOT a claim about their full capacity.
 * Exclusive REU ownership is required, including during the reversible probe.
 * Saves/restores a byte at $100 in each of the first eight expansion banks.
 * Returns errno; publishes capacity only after complete restoration succeeds. */
extern unsigned char udeks_reu_capacity_banks; /* usable 64 KiB banks: 0/2/4/8 */
unsigned char udeks_reu_discover(void);

#endif
