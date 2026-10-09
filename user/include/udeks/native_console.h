/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_NATIVE_CONSOLE_H
#define UDEKS_NATIVE_CONSOLE_H

#include "udeks/program.h"

/* Experimental cooperative console runtime, using existing UTRQ operations.
 * WRITE accepts stdout/stderr or mounted-file fd 4, up to 24 bytes per request.
 * SLEEP accepts 1..600 logical 1/60-second ticks; returns 0 or IO_ERROR.
 * READ is canonical foreground stdin (54 characters plus newline) or fd 4,
 * in chunks of 1..24 bytes. Only stdin sleeps through POLL.
 * POLL accepts 0..600 ticks or POLL_FOREVER; background READ/POLL returns EIO.
 * OPEN supports RDONLY/CREATE_EXCL paths of 1..23 bytes. File READ returns 0
 * at EOF; CLOSE must be checked, even after a failed/short WRITE. No write
 * retries/overwrite. One service-wide file stream: contention returns EMFILE.
 * Sleep between file chunks to let peers run. An individual IEC request is
 * synchronous; EXIT/CANCEL closes owned files before task-slot reuse.
 * No raw input, EOF key, native directory enumeration or bank-0 veneers.
 * Entry receives bounded task-private argc/argv via UARG 0.1 (see executable
 * ABI): at most 8 arguments, within the shell's 54-character input line.
 * Ordinary foreground return becomes the shell's eight-bit exit status.
 * This runtime requires an argument-enabled kernel; old kernels return 126. */
unsigned char udeks_sleep(unsigned int ticks);

#endif
