/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_IPC_H
#define UDEKS_IPC_H
/* UTRQ 0.21 operation 29. Descriptor selects suboperation, flags zero.
 * Handle words are little endian. See abi/ipc.md; SDK follows in slice 2. */
#define UDEKS_IPC_ENDPOINTS       2u
#define UDEKS_IPC_NAME_MAX        8u
#define UDEKS_IPC_MESSAGE_MAX    16u
#define UDEKS_IPC_CREATE          0u
#define UDEKS_IPC_LOOKUP          1u
#define UDEKS_IPC_SEND            2u
#define UDEKS_IPC_RECEIVE         3u
#define UDEKS_IPC_CLOSE           4u
#define UDEKS_IPC_HANDLE          0u
#define UDEKS_IPC_SEND_SOURCE     2u
#define UDEKS_IPC_SEND_DATA       4u
#define UDEKS_IPC_RECEIVE_CAPACITY 2u
#define UDEKS_IPC_REPLY_SOURCE    0u
#define UDEKS_IPC_REPLY_DATA      2u
#define UDEKS_IPC_EACCES         13u
#define UDEKS_IPC_EEXIST         17u
#define UDEKS_IPC_ENOSPC         28u
#define UDEKS_IPC_EMSGSIZE       90u
#endif
