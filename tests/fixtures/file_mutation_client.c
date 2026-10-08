/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Host SDK-to-real-service bridge. No emulated disk writes. */
#include <stdint.h>
#include <string.h>
#include "udeks/task_request.h"
#include "udeks/file_mutation.h"
extern uint8_t udeks_storage_request[38];
extern uint8_t udeks_errno;
uint8_t udeks_storage_dispatch(void);
uint8_t udeks_file_payload[24];
uint8_t test_sdk_calls, test_sdk_operations[8];
uint8_t test_sdk_close_error;
extern uint8_t test_close_error;

static uint8_t submit(uint8_t op, uint8_t fd, uint8_t count, uint8_t minor)
{
    uint8_t handled;
    if (test_sdk_calls < 8) test_sdk_operations[test_sdk_calls] = op;
    ++test_sdk_calls;
    memset(udeks_storage_request, 0, 38);
    memcpy(udeks_storage_request, "UTRQ", 4);
    udeks_storage_request[5] = minor;
    udeks_storage_request[6] = 1;
    udeks_storage_request[7] = op & 127u;
    udeks_storage_request[13] = op >> 7;
    udeks_storage_request[9] = fd;
    udeks_storage_request[10] = count;
    memcpy(udeks_storage_request+14, udeks_file_payload, 24);
    if (op == UDEKS_TREQ_OP_CLOSE) test_close_error = test_sdk_close_error;
    handled = udeks_storage_dispatch();
    memcpy(udeks_file_payload, udeks_storage_request+14, 24);
    udeks_errno = udeks_storage_request[12];
    if (!handled) udeks_errno = 38;
    return udeks_errno ? 255 : udeks_storage_request[11];
}
uint8_t udeks_fs_request(uint8_t op, uint8_t fd, uint8_t count)
{ return submit(op, fd, count, 14); }
uint8_t udeks_mutation_request(uint8_t op, uint8_t fd, uint8_t count)
{ return submit(op, fd, count, UDEKS_FILE_MUTATION_MINOR); }
