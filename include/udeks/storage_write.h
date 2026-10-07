/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private integration contract. NOT an advertised syscall ABI yet. */
#ifndef UDEKS_STORAGE_WRITE_H
#define UDEKS_STORAGE_WRITE_H
#include <stdint.h>
#include "udeks/compiler.h"

#define UDEKS_STORAGE_WRITE_MINOR 14u
#define UDEKS_STORAGE_OPEN_CREATE 3u
#define UDEKS_STORAGE_MOUNT_RW 1u
#define UDEKS_STORAGE_MOUNT_REMOUNT 2u

/* Supplied by the trusted request/loader boundary, never by request bytes.
 * Nonzero identity of the calling instance (including synchronous console
 * executions), not just a reusable task slot. Zero means no valid caller.
 * The integration must call cleanup BEFORE reclaim/reuse; it must not reuse
 * an identity while that identity owns a handle, including counter wrap.
 * The private bank-1 lease supplies it from its trusted AX argument; scheduler
 * and foreground-loader providers are not wired into production yet. */
uint16_t udeks_storage_caller(void);

/* Trusted exit/cancel hook. Close an instance's handle, return finalization
 * errno and release ownership even on failure. Non-owner/no handle is a no-op.
 * Does not alter the shared request/response. Must run in the storage context,
 * serialized with dispatch, while the owner and transport are still valid. */
uint8_t UDEKS_FASTCALL udeks_storage_cleanup(uint16_t instance);
#endif
