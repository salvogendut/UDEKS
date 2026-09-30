/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_IEC_SLOW_H
#define UDEKS_IEC_SLOW_H
#include <stdint.h>
#include "udeks/compiler.h"

/* Private, single-owner storage-service transport. The service must call this
 * only with the kernel-I/O MMU profile; no KERNAL vectors are used. */
#define UDEKS_IEC_OK       0u
#define UDEKS_IEC_EOI      1u
#define UDEKS_IEC_TIMEOUT  2u
#define UDEKS_IEC_NO_DEVICE 3u
#define UDEKS_IEC_BAD_STATE 4u

/* Open DOS directory "$" on channel 0 of device 8..11. A failed open
 * releases ATN, CLK, and DATA and leaves no active transaction. */
uint8_t UDEKS_FASTCALL udeks_iec_open_directory(uint8_t device);
/* Set a 1..16-byte DOS filename before opening channel 2. The transport
 * copies no caller-owned memory: the single service owner fills this buffer
 * and length while idle, then calls open_file(device). Names are PETSCII;
 * path conversion and validation belong to the storage service. */
extern uint8_t udeks_iec_filename[16];
extern uint8_t udeks_iec_filename_length;
uint8_t UDEKS_FASTCALL udeks_iec_open_file(uint8_t device);
/* Low byte is data; high byte is OK, EOI, TIMEOUT, or BAD_STATE. The EOI
 * byte itself is valid and must be consumed before closing the channel. */
uint16_t udeks_iec_read_byte(void);
uint8_t udeks_iec_close(void);
#endif
