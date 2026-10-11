/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_NATIVE_IPC_H
#define UDEKS_NATIVE_IPC_H
#include "udeks/program.h"
#include "udeks/ipc.h"
/* Native bank-1 tasks only. All calls are synchronous and nonblocking.
 * Names are NUL-terminated ASCII strings of 1..8 bytes. Handles never repeat
 * within a boot. CREATE/LOOKUP return 0 on error and set udeks_errno.
 * SEND/CLOSE return 0 on success, UDEKS_IO_ERROR on error.
 * RECEIVE returns 1..16 copied bytes or UDEKS_IO_ERROR; sender and buffer
 * remain untouched on error. A zero capacity is valid (no buffer required).
 * Use task-private buffers; calls borrow the common request record.
 * There are no implicit retries, yields, timeouts or endpoint cleanup here;
 * callers handle EAGAIN and close their endpoints. EXIT/CANCEL also retire
 * owned endpoints. See abi/ipc.md for queue, lifetime and exhaustion rules. */
typedef unsigned int udeks_ipc_handle;
udeks_ipc_handle udeks_ipc_create(const unsigned char *name);
udeks_ipc_handle udeks_ipc_lookup(const unsigned char *name);
unsigned char udeks_ipc_send(udeks_ipc_handle destination,
                            udeks_ipc_handle source,
                            const unsigned char *buffer, unsigned char count);
unsigned char udeks_ipc_receive(udeks_ipc_handle endpoint,
                               udeks_ipc_handle *sender,
                               unsigned char *buffer, unsigned char capacity);
unsigned char udeks_ipc_close(udeks_ipc_handle endpoint);
#endif
