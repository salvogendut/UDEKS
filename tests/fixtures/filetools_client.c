/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/program.h"
#include "udeks/task_request.h"

unsigned char filetools_payload[24], filetools_cwd, filetools_error;
unsigned char test_input[512], test_output[1024], test_error[128];
unsigned short test_length, test_position, test_output_length, test_error_length;
unsigned char test_calls, test_closes, test_failure_op, test_dents, test_errno;
unsigned char test_op, test_fd, test_count, test_payload[24];
char test_open_path[24], test_stat_path[24];

void test_reset(void)
{
    filetools_cwd = test_calls = test_closes = test_failure_op = test_dents = 0;
    filetools_error = 0;
    test_errno = UDEKS_TREQ_EIO;
    test_length = test_position = test_output_length = test_error_length = 0;
    test_open_path[0] = test_stat_path[0] = 0;
}

unsigned char udeks_write_byte(unsigned char fd, unsigned char c)
{
    if (fd == 1 && test_output_length < sizeof(test_output)) test_output[test_output_length++] = c;
    else if (fd == 2 && test_error_length < sizeof(test_error)) test_error[test_error_length++] = c;
    else return UDEKS_IO_ERROR;
    return 0;
}

unsigned char udeks_write(unsigned char fd, const unsigned char *text)
{
    while (*text) udeks_write_byte(fd, *text++);
    return 0;
}

unsigned char file_request(unsigned char op, unsigned char fd, unsigned char count)
{
    unsigned char n;
    ++test_calls;
    test_op = op; test_fd = fd; test_count = count;
    memcpy(test_payload, filetools_payload, 24);
    if (op == UDEKS_TREQ_OP_CLOSE) ++test_closes;
    filetools_error = op == test_failure_op ? test_errno : 0;
    if (filetools_error) return UDEKS_IO_ERROR;
    switch (op) {
    case UDEKS_TREQ_OP_OPEN:
        memcpy(test_open_path, filetools_payload, 24);
        return 4;
    case UDEKS_TREQ_OP_READ:
        n = test_length - test_position > count ? count : test_length - test_position;
        memcpy(filetools_payload, test_input + test_position, n);
        test_position += n;
        return n;
    case UDEKS_TREQ_OP_GETDENTS:
        if (test_dents++) return 0;
        memcpy(filetools_payload, "\x08\x05HELLO", 7);
        return 7;
    case UDEKS_TREQ_OP_STAT:
        memcpy(test_stat_path, filetools_payload, 24);
        memcpy(filetools_payload, "\x08\x0c\x00", 3);
        return 3;
    default: return 0;
    }
}
