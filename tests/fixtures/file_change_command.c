/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/program.h"
#include "udeks/file_mutation.h"
unsigned char udeks_errno, test_result, test_operation, test_calls;
unsigned char test_bad_descriptor, test_source[64], test_destination[64];
unsigned char test_output[256];

unsigned char udeks_write(unsigned char fd, const unsigned char *text)
{
    if (fd != 2) test_bad_descriptor = 1;
    if (strlen((char *)test_output) + strlen((const char *)text) < sizeof(test_output))
        strcat((char *)test_output, (const char *)text);
    return 0;
}
unsigned char udeks_write_byte(unsigned char fd, unsigned char value)
{
    unsigned char text[2]; text[0] = value; text[1] = 0;
    return udeks_write(fd, text);
}
static unsigned char call(unsigned char op, const unsigned char *a, const unsigned char *b)
{
    ++test_calls; test_operation = op;
    strncpy((char *)test_source, (const char *)a, 63);
    if (b) strncpy((char *)test_destination, (const char *)b, 63);
    return test_result;
}
unsigned char udeks_rename(const unsigned char *a, const unsigned char *b)
{ return call(UDEKS_FILE_RENAME, a, b); }
unsigned char udeks_copy(const unsigned char *a, const unsigned char *b)
{ return call(UDEKS_FILE_COPY, a, b); }
unsigned char udeks_unlink(const unsigned char *a)
{ return call(UDEKS_FILE_UNLINK, a, 0); }
