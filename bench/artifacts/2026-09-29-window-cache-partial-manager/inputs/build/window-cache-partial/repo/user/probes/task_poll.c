/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Qualification task: real cc65 locals survive finite/infinite input waits. */
#include "udeks/program.h"
#include "udeks/task_request.h"

#define DIAG ((volatile unsigned char *)0xF040u)
#define REQ ((volatile unsigned char *)UDEKS_TASK_REQUEST_BASE)
static unsigned char done;

static void require(unsigned char condition, unsigned char code)
{
    if (!condition) {
        DIAG[5] = code;
        DIAG[4] = 0xEE;
        for (;;) {}
    }
}

static void invalid(unsigned char minor, unsigned char descriptor,
                    unsigned char count, unsigned char flags,
                    unsigned int mask, unsigned int timeout,
                    unsigned char error)
{
    unsigned char sequence;
    sequence = REQ[UDEKS_TREQ_SEQUENCE];
    REQ[UDEKS_TREQ_MINOR] = minor;
    REQ[UDEKS_TREQ_DESCRIPTOR] = descriptor;
    REQ[UDEKS_TREQ_COUNT] = count;
    REQ[UDEKS_TREQ_FLAGS] = flags;
    REQ[UDEKS_TREQ_PAYLOAD] = (unsigned char)mask;
    REQ[UDEKS_TREQ_PAYLOAD + 1] = (unsigned char)(mask >> 8);
    REQ[UDEKS_TREQ_PAYLOAD + 2] = (unsigned char)timeout;
    REQ[UDEKS_TREQ_PAYLOAD + 3] = (unsigned char)(timeout >> 8);
    REQ[UDEKS_TREQ_STATE] = UDEKS_TREQ_STATE_REQUEST;
    ((unsigned char (*)(void))0xFF16u)();
    require(REQ[UDEKS_TREQ_STATE] == UDEKS_TREQ_STATE_ERROR &&
            REQ[UDEKS_TREQ_ERROR] == error &&
            REQ[UDEKS_TREQ_SEQUENCE] == sequence &&
            REQ[UDEKS_TREQ_PAYLOAD] == (unsigned char)mask &&
            REQ[UDEKS_TREQ_PAYLOAD + 1] == (unsigned char)(mask >> 8) &&
            REQ[UDEKS_TREQ_PAYLOAD + 2] == (unsigned char)timeout &&
            REQ[UDEKS_TREQ_PAYLOAD + 3] == (unsigned char)(timeout >> 8), 1);
}

unsigned char udeks_ush_poll(void)
{
    unsigned char guard[16];
    unsigned char buffer[8];
    unsigned char index;
    unsigned char sequence;
    if (done) return 0;
    for (index = 0; index < sizeof(guard); ++index) guard[index] = 0xA0 + index;
    DIAG[0] = 'U'; DIAG[1] = 'P'; DIAG[2] = 'O'; DIAG[3] = 'L';
    DIAG[5] = 0;
    DIAG[7] = 0;
    *(volatile unsigned char *)0xF3D9u = UDEKS_USH_STATE_READY;
    require(udeks_poll(UDEKS_STDIN, 0) == 0 && udeks_errno == 0, 2);
    invalid(3, 0, 4, 0, 1, 0, UDEKS_TREQ_ENOSYS);
    invalid(5, 0, 4, 0, 1, 0, UDEKS_TREQ_EPROTO);
    invalid(4, 1, 4, 0, 1, 0, UDEKS_TREQ_EBADF);
    invalid(4, 0, 3, 0, 1, 0, UDEKS_TREQ_EINVAL);
    invalid(4, 0, 4, 1, 1, 0, UDEKS_TREQ_EINVAL);
    invalid(4, 0, 4, 0, 0, 0, UDEKS_TREQ_EINVAL);
    invalid(4, 0, 4, 0, 0x0101, 0, UDEKS_TREQ_EINVAL);
    invalid(4, 0, 4, 0, 1, 601, UDEKS_TREQ_EINVAL);
    invalid(4, 0, 4, 0, 1, 0xFFFE, UDEKS_TREQ_EINVAL);
    DIAG[4] = 1;
    while (DIAG[6] != 0xA1) {}
    require(udeks_poll(UDEKS_STDIN, 10) == 0 && udeks_errno == 0, 3);
    require(REQ[UDEKS_TREQ_PAYLOAD + 2] == 10 &&
            REQ[UDEKS_TREQ_PAYLOAD + 3] == 0, 4);
    DIAG[4] = 2;
    require(udeks_poll(UDEKS_STDIN, UDEKS_TREQ_POLL_FOREVER) == 1, 5);
    require(udeks_poll(UDEKS_STDIN, 0) == 1, 6); /* did not consume */
    require(udeks_read(UDEKS_STDIN, buffer, 3) == 3 &&
            buffer[0] == 'h' && buffer[1] == 'e' && buffer[2] == 'l', 7);
    require(udeks_poll(UDEKS_STDIN, 0) == 1, 8); /* partial read */
    require(udeks_read(UDEKS_STDIN, buffer, 8) == 3 &&
            buffer[0] == 'l' && buffer[1] == 'o' && buffer[2] == '\n', 9);
    require(udeks_poll(UDEKS_STDIN, 0) == 0, 10);
    sequence = REQ[UDEKS_TREQ_SEQUENCE] + 1;
    DIAG[4] = 3;
    require(udeks_poll(UDEKS_STDIN, UDEKS_TREQ_POLL_FOREVER) == 1, 11);
    require(REQ[UDEKS_TREQ_SEQUENCE] == sequence &&
            REQ[UDEKS_TREQ_FLAGS] == 0 &&
            REQ[UDEKS_TREQ_PAYLOAD + 1] == 0 &&
            REQ[UDEKS_TREQ_PAYLOAD + 2] == 0xFF &&
            REQ[UDEKS_TREQ_PAYLOAD + 3] == 0xFF, 12);
    require(udeks_read(UDEKS_STDIN, buffer, 8) == 1 && buffer[0] == '\n', 13);
    require(udeks_poll(UDEKS_STDIN, 0) == 0, 14);
    for (index = 0; index < sizeof(guard); ++index)
        require(guard[index] == (unsigned char)(0xA0 + index), 15);
    done = 1;
    DIAG[4] = 0xA5;
    return 0;
}
