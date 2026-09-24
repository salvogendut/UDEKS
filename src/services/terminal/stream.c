/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/root_console.h"
#include "udeks/stream.h"

unsigned char udeks_stream_write_byte(
    unsigned char descriptor, unsigned char value)
{
    if (descriptor != UDEKS_STDOUT && descriptor != UDEKS_STDERR) {
        return UDEKS_STREAM_BAD_DESCRIPTOR;
    }
    udeks_root_console_write(value);
    return UDEKS_STREAM_OK;
}

unsigned char udeks_stream_write(
    unsigned char descriptor, const unsigned char *text)
{
    if (descriptor != UDEKS_STDOUT && descriptor != UDEKS_STDERR) {
        return UDEKS_STREAM_BAD_DESCRIPTOR;
    }
    udeks_root_console_write_string(text);
    return UDEKS_STREAM_OK;
}
