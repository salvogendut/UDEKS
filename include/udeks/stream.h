/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_STREAM_H
#define UDEKS_STREAM_H

#define UDEKS_STDIN                     0u
#define UDEKS_STDOUT                    1u
#define UDEKS_STDERR                    2u

#define UDEKS_STREAM_OK                 0u
#define UDEKS_STREAM_BAD_DESCRIPTOR     1u

unsigned char udeks_stream_write_byte(
    unsigned char descriptor, unsigned char value);
unsigned char udeks_stream_write(
    unsigned char descriptor, const unsigned char *text);

#endif
