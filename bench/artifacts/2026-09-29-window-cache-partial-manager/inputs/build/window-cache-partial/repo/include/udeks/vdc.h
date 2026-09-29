/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_VDC_H
#define UDEKS_VDC_H

#include "udeks/compiler.h"

#define UDEKS_VDC_OK             0u
#define UDEKS_VDC_TIMEOUT        1u

/*
 * Serialized microkernel transport for the VDC's indirect $D600/$D601 port.
 * Callers select a register, then read or write it. Every operation has a
 * bounded ready wait and updates udeks_vdc_status.
 */
extern volatile unsigned char udeks_vdc_status;
extern const unsigned char *udeks_vdc_block_source;
extern unsigned int udeks_vdc_block_address;
extern unsigned int udeks_vdc_block_length;

unsigned char UDEKS_FASTCALL udeks_vdc_select(unsigned char reg);
unsigned char UDEKS_FASTCALL udeks_vdc_write_selected(unsigned char value);
unsigned char udeks_vdc_read_selected(void);
unsigned char udeks_vdc_write_block(void);

#endif
