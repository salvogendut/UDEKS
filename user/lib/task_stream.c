/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/program.h"
#include "udeks/task_bank.h"
#include "udeks/task_request.h"

#define REQUEST_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + (offset)))

typedef unsigned char (*task_request_gate)(void);

unsigned char udeks_errno;
static unsigned char request_sequence;

static unsigned char submit_request(
    unsigned char operation, unsigned char descriptor,
    unsigned char count)
{
    task_request_gate gate;

    ++request_sequence;
    REQUEST_BYTE(UDEKS_TREQ_MAGIC0) = 'U';
    REQUEST_BYTE(UDEKS_TREQ_MAGIC1) = 'T';
    REQUEST_BYTE(UDEKS_TREQ_MAGIC2) = 'R';
    REQUEST_BYTE(UDEKS_TREQ_MAGIC3) = 'Q';
    REQUEST_BYTE(UDEKS_TREQ_MAJOR) = UDEKS_TASK_REQUEST_ABI_MAJOR;
    REQUEST_BYTE(UDEKS_TREQ_MINOR) = UDEKS_TASK_REQUEST_ABI_MINOR;
    REQUEST_BYTE(UDEKS_TREQ_OPERATION) = operation;
    REQUEST_BYTE(UDEKS_TREQ_SEQUENCE) = request_sequence;
    REQUEST_BYTE(UDEKS_TREQ_DESCRIPTOR) = descriptor;
    REQUEST_BYTE(UDEKS_TREQ_COUNT) = count;
    REQUEST_BYTE(UDEKS_TREQ_RESULT) = 0;
    REQUEST_BYTE(UDEKS_TREQ_ERROR) = 0;
    REQUEST_BYTE(UDEKS_TREQ_FLAGS) = 0;
    REQUEST_BYTE(UDEKS_TREQ_STATE) = UDEKS_TREQ_STATE_REQUEST;
    gate = (task_request_gate)UDEKS_TASK_BANK_REQUEST;
    gate();
    if (REQUEST_BYTE(UDEKS_TREQ_STATE) != UDEKS_TREQ_STATE_COMPLETE) {
        udeks_errno = REQUEST_BYTE(UDEKS_TREQ_ERROR);
        return UDEKS_IO_ERROR;
    }
    udeks_errno = 0;
    return REQUEST_BYTE(UDEKS_TREQ_RESULT);
}

unsigned char udeks_write_byte(
    unsigned char descriptor, unsigned char value)
{
    REQUEST_BYTE(UDEKS_TREQ_PAYLOAD) = value;
    return submit_request(UDEKS_TREQ_OP_WRITE, descriptor, 1u) == 1u ? 0u : 1u;
}

unsigned char udeks_write(
    unsigned char descriptor, const unsigned char *text)
{
    unsigned char count;
    unsigned char index;

    while (*text != 0) {
        count = 0;
        while (count < UDEKS_TASK_REQUEST_PAYLOAD_SIZE && text[count] != 0) {
            REQUEST_BYTE(UDEKS_TREQ_PAYLOAD + count) = text[count];
            ++count;
        }
        if (submit_request(UDEKS_TREQ_OP_WRITE, descriptor, count) != count) {
            return 1u;
        }
        for (index = 0; index < count; ++index) {
            ++text;
        }
    }
    return 0u;
}

unsigned char udeks_read(
    unsigned char descriptor, unsigned char *buffer, unsigned char count)
{
    unsigned char result;
    unsigned char index;

    if (count > UDEKS_TASK_REQUEST_PAYLOAD_SIZE) {
        count = UDEKS_TASK_REQUEST_PAYLOAD_SIZE;
    }
    result = submit_request(UDEKS_TREQ_OP_READ, descriptor, count);
    if (result == UDEKS_IO_ERROR) {
        return result;
    }
    for (index = 0; index < result; ++index) {
        buffer[index] = REQUEST_BYTE(UDEKS_TREQ_PAYLOAD + index);
    }
    return result;
}

unsigned char udeks_exec_line(
    const unsigned char *line, unsigned char length)
{
    volatile unsigned char *command;
    unsigned char index;

    if (length == 0 || length >= UDEKS_TASK_COMMAND_SIZE) {
        udeks_errno = UDEKS_TREQ_EINVAL;
        return UDEKS_IO_ERROR;
    }
    command = (volatile unsigned char *)UDEKS_TASK_COMMAND_BASE;
    for (index = 0; index < length; ++index) {
        command[index] = line[index];
    }
    command[length] = 0;
    return submit_request(UDEKS_TREQ_OP_EXEC, 0, length);
}

unsigned char udeks_wait_foreground(void)
{
    return submit_request(UDEKS_TREQ_OP_WAIT, 0, 0);
}

unsigned char udeks_prompt(void)
{
    return submit_request(UDEKS_TREQ_OP_PROMPT, 0, 0);
}
