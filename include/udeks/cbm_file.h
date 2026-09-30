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
#endif
