/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
unsigned char udeks_file_payload[24], test_payload[24];
unsigned char test_op, test_fd, test_count, test_calls, test_result, test_error;
extern unsigned char udeks_errno;
unsigned char udeks_fs_request(unsigned char op, unsigned char fd, unsigned char count)
{
    test_op=op; test_fd=fd; test_count=count; ++test_calls;
    memcpy(test_payload,udeks_file_payload,24);
    udeks_errno=test_error;
    return test_result;
}
