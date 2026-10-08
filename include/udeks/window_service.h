/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_WINDOW_SERVICE_H
#define UDEKS_WINDOW_SERVICE_H

/* Private resident service query for the forthcoming banked graphics router.
 * This is NOT an added UAPP vector. The router must derive caller ownership
 * from its task/slot record, never trust an owner supplied in a request. */
unsigned char __fastcall__ udeks_window_owner(unsigned char handle);
/* Private service preflight. Frozen drag/capture/paste pixels cannot accept
 * a delta yet. No state is mutated; the client may sleep and retry. */
unsigned char udeks_window_update_busy(void);

#endif
