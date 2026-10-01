/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_WINDOW_SERVICE_H
#define UDEKS_WINDOW_SERVICE_H

/* Private resident service query for the forthcoming banked graphics router.
 * This is NOT an added UAPP vector. The router must derive caller ownership
 * from its task/slot record, never trust an owner supplied in a request. */
unsigned char __fastcall__ udeks_window_owner(unsigned char handle);

#endif
