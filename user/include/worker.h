/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_USER_WORKER_H
#define UDEKS_USER_WORKER_H
/* Requires a request veneer built for ABI 0.11. Write four UTRQ payload
 * bytes: mailbox opcode (0/4/5), arg0, arg1, output length (0..64).
 * Returns errno, not a pointer. On success payload[0..2] is result LE16,
 * output length; copy that many bytes from this READ-ONLY borrowed array to
 * private memory immediately, BEFORE another request or any yield. */
extern unsigned char worker_request(void);
extern volatile unsigned char udeks_worker_output[64];
#endif
