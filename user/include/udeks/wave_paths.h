/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_USER_WAVE_PATHS_H
#define UDEKS_USER_WAVE_PATHS_H
#define UDEKS_WAVE_SAMPLES 525u
#define UDEKS_WAVE_PATH_BYTES 1128u
struct udeks_wave_projection {
    unsigned int width, used, previous_x, previous_y;
    unsigned char height, axis, strip, point, done;
};
extern struct udeks_wave_projection udeks_wave_projection_state;
unsigned char udeks_wave_paths_begin(unsigned int width, unsigned char height);
/* At most sixteen table-projected vertices per call; no publication until
 * done is set. Input is the fixed opcode-5 sinc field (vertical index 0..75). */
unsigned char udeks_wave_paths_step(const signed char *heights, unsigned char *output);
/* App-owned projection: all 524 edges of the legacy sinc grid, in 24 paths.
 * Input is the worker's 21x25 signed-byte height field. No CPU lease here. */
unsigned int udeks_wave_paths(const signed char *heights, unsigned int width,
    unsigned char height, unsigned char *output);
#endif
