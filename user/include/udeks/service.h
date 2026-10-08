/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_USER_SERVICE_H
#define UDEKS_USER_SERVICE_H
/* Experimental issue #49 interface, NOT enabled by normal boot yet.
 * Only synchronous foreground commands may use this serialized slot. */
#define UDEKS_SERVICE_STATUS 0u
#define UDEKS_SERVICE_BEGIN  1u
#define UDEKS_SERVICE_COMMIT 2u
#define UDEKS_SERVICE_STOP   3u
#define UDEKS_SERVICE_BASE   0x93d0u
#define UDEKS_SERVICE_LIMIT  0x96a8u
#define UDEKS_SERVICE_CAPACITY (UDEKS_SERVICE_LIMIT-UDEKS_SERVICE_BASE)
/* Returns state: 0 offline, 1 loading, 2 published; or IO_ERROR + errno.
 * received is the ACTUAL file length, used only by COMMIT. A successful
 * BEGIN grants this foreground invocation a lease until COMMIT/STOP/exit.
 * Check support/begin BEFORE touching the slot, especially on old kernels.
 * The veneer preserves the caller's ZP and lends its software stack to the
 * root-layout module for the duration of this non-scheduling request. */
unsigned char __fastcall__ udeks_service_control(unsigned char action, unsigned int received);
#endif
