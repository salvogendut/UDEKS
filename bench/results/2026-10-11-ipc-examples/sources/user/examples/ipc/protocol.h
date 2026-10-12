/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef IPC_DEMO_PROTOCOL_H
#define IPC_DEMO_PROTOCOL_H
#define IPC_DEMO_DATA 1u
#define IPC_DEMO_REPLY 2u
#define IPC_DEMO_STOP 3u
#define IPC_DEMO_STOPPED 4u
#define IPC_DEMO_ACK 5u
/* One type byte plus at most 15 data bytes; each client owns a fresh endpoint.
 * The source handle authenticates the peer lifetime. No shared app memory. */
#define IPC_DEMO_WAIT 600u
#endif
