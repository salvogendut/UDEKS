/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CBM_WRITE_H
#define UDEKS_CBM_WRITE_H
#include <stdint.h>

/* PRIVATE storage backend, not a syscall or an app ABI. Probe-only for now.
 * The caller must exclusively own the IEC service (including the reader),
 * validate mount permission and finish a case-folded directory collision
 * scan BEFORE create. DOS also rejects an existing exact name: never use @.
 * Names here are canonical physical upper-case ASCII/PETSCII, not paths.
 * Only new SEQ files; bytes are counted, without a PRG header or encoding. */
#define UDEKS_CBM_WRITE_MAX 24u
#define UDEKS_CBM_ENOSPC 28u
#define UDEKS_CBM_EROFS  30u
uint8_t udeks_cbm_create(uint8_t device, const uint8_t *name, uint8_t length);
uint8_t udeks_cbm_write(const uint8_t *data, uint8_t count);
uint8_t udeks_cbm_write_close(void);

/* WRITE returns errno AND the acknowledged prefix below. An acknowledgement
 * is not durability. A failed byte may have reached the drive; never retry
 * after an error. Errors stick until checked CLOSE, which releases ownership
 * even on failure. Invalid counts/pointers do not poison an existing handle.
 * CLOSE is required for empty files too. After successful zero-data CREATE /
 * CLOSE, a bounded direct-access finalizer corrects DOS's synthetic CR length
 * to zero; it never runs after a failed operation or a nonempty write.
 * This remains probe-only until service integration is qualified.
 * Cancellation must also call CLOSE;
 * a partial/splat file can remain, with no rollback or automatic scratch. */
extern uint8_t udeks_cbm_written;
extern uint8_t udeks_cbm_write_dos_error;
#endif
