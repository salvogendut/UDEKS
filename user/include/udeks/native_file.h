/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_NATIVE_FILE_H
#define UDEKS_NATIVE_FILE_H
/* Native-task UTRQ 0.14+, through FF16 with private cc65 state, NOT the
 * synchronous argc/argv console gate. Set descriptor, count and payload in
 * this record before calling. Returns errno (0 success); result is byte 11.
 * Check CLOSE too. One global disk stream; no automatic retry or overwrite.
 * OPEN_CREATE_PRG needs UTRQ 0.16; ordinary OPEN_CREATE remains SEQ. */
extern volatile unsigned char udeks_graphics_record[38];
unsigned char __fastcall__ native_file_request(unsigned char op);
#endif
