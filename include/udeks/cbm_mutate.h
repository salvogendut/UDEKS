/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CBM_MUTATE_H
#define UDEKS_CBM_MUTATE_H
#include <stdint.h>

#define UDEKS_CBM_RENAME 1u
#define UDEKS_CBM_COPY   2u
#define UDEKS_CBM_REMOVE 3u

/* PRIVATE backend, not a raw-command syscall. Requires exclusive ownership
 * and service preflight: a unique, closed, unlocked SEQ/PRG source, a writable
 * volume, and (for COPY/RENAME) no destination/namespace collision. Only the
 * same disk is supported. Names are exactly 16 bytes, A0 padded; no wildcards.
 * destination must be NULL for REMOVE. All rejection precedes transport.
 * COPY requires a NONEMPTY source: stock DOS turns an empty source into one
 * CR byte. After proving a source empty, use the existing exclusive-create /
 * checked-close path with its source type instead (that path fixes DOS's CR).
 * A transport/DOS failure may follow partial disk mutation: never retry it.
 * The C oracle is synchronous; the compact production backend has a bounded
 * status continuation (below) instead of the private benchmark's long wait. */
uint8_t udeks_cbm_mutate(uint8_t device, uint8_t operation,
    const uint8_t *source, const uint8_t *destination);
/* Service implementation returns EAGAIN while DOS is busy. Poll only after
 * that result, without rebuilding or resending the command. finish aborts
 * the held transport (it cannot roll back a command already sent). */
uint8_t udeks_cbm_mutate_poll(void);
void udeks_cbm_mutate_abort(void);
#endif
