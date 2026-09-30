/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
unsigned char test_device, test_operation, test_error, test_calls, test_descriptor;
char test_message[80];
unsigned char udeks_mount_request(unsigned char device, unsigned char op)
{
    test_device = device;
    test_operation = op;
    ++test_calls;
    return test_error;
}
unsigned char udeks_write(unsigned char descriptor, const unsigned char *text)
{
    test_descriptor = descriptor;
    strncpy(test_message, (const char *)text, sizeof(test_message)-1);
    return 0;
}
