/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CBM_FILE_H
#define UDEKS_CBM_FILE_H
#include <stdint.h>
/* Private, serialized CBM-DOS service; streams sectors without a 256-byte
 * host buffer. Public stream/handle policy remains in iec_service.c. */
extern uint8_t udeks_cbm_entry[30];
uint8_t udeks_cbm_begin(uint8_t device);
uint8_t udeks_cbm_next(void); /* 1 entry, 0 end, 255 error */
uint8_t udeks_cbm_select(void); /* current entry -> file; errno or zero */
uint16_t udeks_cbm_read(void); /* data 0..255, 256 EOF, 512 error */
uint8_t udeks_cbm_close(void);
extern uint16_t udeks_cbm_total_blocks, udeks_cbm_free_blocks;
uint8_t udeks_cbm_space(uint8_t device); /* closed on every return; 0 or EIO */
#ifdef UDEKS_IEC_WRITE
/* Writer-internal finalization, NOT a general truncate primitive. Only after
 * our successful exclusive CREATE + zero data + checked CLOSE. Name is 16
 * canonical, A0-padded physical bytes. Validates the complete directory and
 * a one-block closed SEQ containing only CR, then changes its length to zero.
 * No allocation, BAM or directory writes. Never call for an existing file. */
uint8_t udeks_cbm_finish_empty(uint8_t device, const uint8_t *name);
extern uint8_t udeks_cbm_dos_error;
#endif
#endif
