/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_IEC_SLOW_H
#define UDEKS_IEC_SLOW_H
#include <stdint.h>
#include "udeks/compiler.h"

/* Private, single-owner storage-service transport. The service must call this
 * only with an I/O-visible MMU profile (kernel or worker); no KERNAL
 * vectors are used. The bank-1 service owns its private transport state. */
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
#if defined(UDEKS_IEC_MUTATE)
/* Private mutation qualification only: C0: + name + =0: + name. */
#define UDEKS_IEC_FILENAME_MAX 38u
uint8_t UDEKS_FASTCALL udeks_iec_begin_command(uint8_t device);
#elif defined(UDEKS_IEC_WRITE)
/* Probe-only extension: 0: + sixteen-byte name + ,S,W. Not linked into
 * the shipped service until the storage layout and request gate qualify. */
#define UDEKS_IEC_FILENAME_MAX 22u
#else
#define UDEKS_IEC_FILENAME_MAX 16u
#endif
extern uint8_t udeks_iec_filename[UDEKS_IEC_FILENAME_MAX];
extern uint8_t udeks_iec_filename_length;
uint8_t UDEKS_FASTCALL udeks_iec_open_file(uint8_t device);
/* Checked file open: prepare, TALK status 15, consume status, UNTALK, TALK 2.
 * CLOSE ends the entire transaction, including speed restoration, on failure.
 * The caller must serialize all steps; no second channel owner is allowed. */
uint8_t UDEKS_FASTCALL udeks_iec_prepare_file(uint8_t device);
uint8_t udeks_iec_open_status(void);
uint8_t udeks_iec_untalk(void);
uint8_t udeks_iec_talk_file(void);
/* Send the private filename buffer as a DOS command on channel 15. The
 * caller must UNTALK first. This does not open/close the data channel. */
uint8_t udeks_iec_command(void);
/* Low byte is data; high byte is OK, EOI, TIMEOUT, or BAD_STATE. The EOI
 * byte itself is valid and must be consumed before closing the channel. */
uint16_t udeks_iec_read_byte(void);
uint8_t udeks_iec_close(void);
#ifdef UDEKS_IEC_WRITE
uint8_t udeks_iec_listen_file(void);
/* Low byte = data, high byte = 0 (ordinary) or 1 (EOI). */
uint8_t UDEKS_FASTCALL udeks_iec_write_byte(uint16_t value);
uint8_t udeks_iec_unlisten(void);
/* Release lines and restore the original speed AFTER reading CLOSE status.
 * Does not send CLOSE 15 (which would close unrelated drive channels). */
void udeks_iec_finish(void);
#endif
#endif
