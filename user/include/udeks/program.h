/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_USER_PROGRAM_H
#define UDEKS_USER_PROGRAM_H

#define UDEKS_STDIN                     0u
#define UDEKS_STDOUT                    1u
#define UDEKS_STDERR                    2u

#define UDEKS_EXIT_SUCCESS              0u
#define UDEKS_EXIT_FAILURE              1u
#define UDEKS_IO_ERROR                  0xFFu

extern unsigned char udeks_errno;

unsigned char udeks_write_byte(
    unsigned char descriptor, unsigned char value);
unsigned char udeks_write(
    unsigned char descriptor, const unsigned char *text);
unsigned char udeks_read(
    unsigned char descriptor, unsigned char *buffer, unsigned char count);

unsigned char udeks_program_main(
    unsigned char count, unsigned char **arguments);

#endif
