/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_USER_PROGRAM_H
#define UDEKS_USER_PROGRAM_H

#define UDEKS_STDIN                     0u
#define UDEKS_STDOUT                    1u
#define UDEKS_STDERR                    2u

#define UDEKS_EXIT_SUCCESS              0u
#define UDEKS_EXIT_FAILURE              1u
#define UDEKS_IO_ERROR                  0xFFu
#define UDEKS_O_RDONLY                  0x00u
#define UDEKS_O_DIRECTORY               0x01u

extern unsigned char udeks_errno;

unsigned char udeks_write_byte(
    unsigned char descriptor, unsigned char value);
unsigned char udeks_write(
    unsigned char descriptor, const unsigned char *text);
unsigned char udeks_read(
    unsigned char descriptor, unsigned char *buffer, unsigned char count);
unsigned char udeks_exec_line(
    const unsigned char *line, unsigned char length);
unsigned char udeks_wait_foreground(void);
unsigned char udeks_prompt(void);
unsigned char udeks_open(const unsigned char *path, unsigned char flags);
unsigned char udeks_getdents(
    unsigned char descriptor, unsigned char *buffer, unsigned char capacity);
unsigned char udeks_stat(
    const unsigned char *path, unsigned char *status);
unsigned char udeks_close(unsigned char descriptor);

unsigned char udeks_program_main(
    unsigned char count, unsigned char **arguments);

#endif
