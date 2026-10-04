/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_USER_WAVE_PATHS_H
#define UDEKS_USER_WAVE_PATHS_H
#define UDEKS_WAVE_SAMPLES 525u
#define UDEKS_WAVE_PATH_BYTES 1128u
/* App-owned projection: all 524 edges of the legacy sinc grid, in 24 paths.
 * Input is the worker's 21x25 signed-byte height field. No CPU lease here. */
unsigned int udeks_wave_paths(const signed char *heights, unsigned int width,
    unsigned char height, unsigned char *output);
#endif
