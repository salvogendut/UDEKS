/* SPDX-License-Identifier: GPL-3.0-or-later */
/* User-shell startup policy. Uses only the public request/stream boundary. */
#include "udeks/program.h"
#include "udeks/startup.h"
#include "udeks/task_request.h"

#ifdef UDEKS_STARTUP_HOST_TEST
extern unsigned char startup_request[UDEKS_TASK_REQUEST_SIZE];
#define P (startup_request + UDEKS_TREQ_PAYLOAD)
#else
#define P ((volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + UDEKS_TREQ_PAYLOAD))
#endif
unsigned char submit_request(unsigned char op, unsigned char fd, unsigned char count);

static unsigned char script[UDEKS_STARTUP_MAX + 1u];
static unsigned char length, cursor;

unsigned char udeks_startup_begin(unsigned char device)
{
    unsigned char fd, count, i, error, width, c;
    length = cursor = 0;
    P[0] = device;
    for (i = 0; i != 4; ++i) P[i+1] = "/mnt"[i];
    if (submit_request(UDEKS_TREQ_OP_MOUNT, 0, 5) == UDEKS_IO_ERROR)
        return UDEKS_IO_ERROR;
    for (i = 0; i != 8; ++i) P[i] = "/mnt/RC"[i];
    fd = submit_request(UDEKS_TREQ_OP_OPEN, 0, 7);
    error = 0;
    if (fd == UDEKS_IO_ERROR) {
        if (udeks_errno != UDEKS_TREQ_ENOENT) error = 1;
    } else {
        for (;;) {
            count = submit_request(UDEKS_TREQ_OP_READ, fd, 24);
            if (count == UDEKS_IO_ERROR || count > UDEKS_STARTUP_MAX-length) {
                error = 1;
                break;
            }
            if (!count) break;
            for (i = 0; i < count; ++i) script[length++] = P[i];
        }
        if (submit_request(UDEKS_TREQ_OP_CLOSE, fd, 0) == UDEKS_IO_ERROR) error = 1;
    }
    for (i = 0; i != 4; ++i) P[i] = "/mnt"[i];
    if (submit_request(UDEKS_TREQ_OP_UMOUNT, 0, 4) == UDEKS_IO_ERROR) error = 1;
    /* Validate the WHOLE file, including later lines, before running any. */
    width = 0;
    for (i = 0; i < length; ++i) {
        c = script[i];
        if (c == '\n' || c == '\r') width = 0;
        else if ((c < 32 && c != '\t') || c > 126 || ++width > UDEKS_STARTUP_LINE)
            error = 1;
    }
    if (error) { length = 0; return UDEKS_IO_ERROR; }
    return length != 0;
}

unsigned char udeks_startup_next(unsigned char *line)
{
    unsigned char size, c;
    size = 0;
    while (cursor < length) {
        c = script[cursor++];
        if (c == '\n' || c == '\r') {
            if (size) break;
        } else line[size++] = c;
    }
    line[size] = 0;
    return size;
}
