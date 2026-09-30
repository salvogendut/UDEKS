/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/task_request.h"
unsigned char startup_request[38], udeks_errno, test_input[300];
unsigned char test_fail_op, test_error, test_calls[20];
unsigned int test_length, test_cursor;
void test_reset(void)
{
    memset(test_calls, 0, sizeof(test_calls));
    test_fail_op = test_error = udeks_errno = 0;
    test_length = test_cursor = 0;
}
unsigned char submit_request(unsigned char op, unsigned char fd, unsigned char count)
{
    unsigned int n;
    (void)fd;
    ++test_calls[op];
    if (op == test_fail_op) { udeks_errno = test_error; return 255; }
    if (op == 6) return 4;
    if (op != 1) return 0;
    n = test_length-test_cursor;
    if (n > count) n = count;
    memcpy(startup_request+14, test_input+test_cursor, n);
    test_cursor += n;
    return n;
}
