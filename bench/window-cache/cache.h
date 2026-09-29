/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Placement spike only: these calls are not installed in the resident OS. */
#ifndef WINDOW_CACHE_SPIKE_H
#define WINDOW_CACHE_SPIKE_H
unsigned char cache_capture(unsigned int x, unsigned char y,
                            unsigned int width, unsigned char height);
unsigned char cache_paste(unsigned int x, unsigned char y);
void __fastcall__ cache_transfer(unsigned char mode);
void cache_seed_service(void);
#endif
