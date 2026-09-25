/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/program.h"
#include "udeks/syscall.h"
#include "udeks/task_request.h"

#define REQUEST(offset) \
    (*(volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + (offset)))

typedef unsigned char (*request_gate)(void);

unsigned char udeks_errno;
static unsigned char sequence;

static unsigned char submit(
    unsigned char operation, unsigned char descriptor, unsigned char count)
{
    request_gate gate;

    ++sequence;
    REQUEST(UDEKS_TREQ_MAGIC0) = 'U';
    REQUEST(UDEKS_TREQ_MAGIC1) = 'T';
    REQUEST(UDEKS_TREQ_MAGIC2) = 'R';
    REQUEST(UDEKS_TREQ_MAGIC3) = 'Q';
    REQUEST(UDEKS_TREQ_MAJOR) = UDEKS_TASK_REQUEST_ABI_MAJOR;
    REQUEST(UDEKS_TREQ_MINOR) = UDEKS_TASK_REQUEST_ABI_MINOR;
    REQUEST(UDEKS_TREQ_OPERATION) = operation;
    REQUEST(UDEKS_TREQ_SEQUENCE) = sequence;
    REQUEST(UDEKS_TREQ_DESCRIPTOR) = descriptor;
    REQUEST(UDEKS_TREQ_COUNT) = count;
    REQUEST(UDEKS_TREQ_RESULT) = 0;
    REQUEST(UDEKS_TREQ_ERROR) = 0;
    REQUEST(UDEKS_TREQ_FLAGS) = 0;
    REQUEST(UDEKS_TREQ_STATE) = UDEKS_TREQ_STATE_REQUEST;
    /* Transient programs execute in bank 0, where the resident syscall table
     * is directly visible.  The $FF16 bank gateway is exclusively for the
     * persistent bank-1 runtime and would return through the wrong bank here.
     */
    gate = (request_gate)UDEKS_SYSCALL_TASK_REQUEST;
    gate();
    if (REQUEST(UDEKS_TREQ_STATE) != UDEKS_TREQ_STATE_COMPLETE) {
        udeks_errno = REQUEST(UDEKS_TREQ_ERROR);
        return UDEKS_IO_ERROR;
    }
    udeks_errno = 0;
    return REQUEST(UDEKS_TREQ_RESULT);
}

static unsigned char copy_path(const unsigned char *path)
{
    unsigned char length;

    length = 0;
    while (path[length] != 0) {
        if (length == UDEKS_TASK_REQUEST_PAYLOAD_SIZE - 1u) {
            udeks_errno = UDEKS_TREQ_EINVAL;
            return UDEKS_IO_ERROR;
        }
        REQUEST(UDEKS_TREQ_PAYLOAD + length) = path[length];
        ++length;
    }
    REQUEST(UDEKS_TREQ_PAYLOAD + length) = 0;
    return length;
}

unsigned char udeks_open(const unsigned char *path, unsigned char flags)
{
    unsigned char length;

    length = copy_path(path);
    if (length == UDEKS_IO_ERROR) {
        return length;
    }
    return submit(UDEKS_TREQ_OP_OPEN, flags, length);
}

unsigned char udeks_getdents(
    unsigned char descriptor, unsigned char *buffer, unsigned char capacity)
{
    unsigned char result;
    unsigned char index;

    if (capacity > UDEKS_TASK_REQUEST_PAYLOAD_SIZE) {
        capacity = UDEKS_TASK_REQUEST_PAYLOAD_SIZE;
    }
    result = submit(UDEKS_TREQ_OP_GETDENTS, descriptor, capacity);
    if (result == UDEKS_IO_ERROR) {
        return result;
    }
    for (index = 0; index < result; ++index) {
        buffer[index] = REQUEST(UDEKS_TREQ_PAYLOAD + index);
    }
    return result;
}

unsigned char udeks_stat(const unsigned char *path, unsigned char *status)
{
    unsigned char length;
    unsigned char result;
    unsigned char index;

    length = copy_path(path);
    if (length == UDEKS_IO_ERROR) {
        return length;
    }
    result = submit(UDEKS_TREQ_OP_STAT, 0, length);
    if (result == UDEKS_IO_ERROR) {
        return result;
    }
    for (index = 0; index < result; ++index) {
        status[index] = REQUEST(UDEKS_TREQ_PAYLOAD + index);
    }
    return result;
}

unsigned char udeks_close(unsigned char descriptor)
{
    return submit(UDEKS_TREQ_OP_CLOSE, descriptor, 0);
}
