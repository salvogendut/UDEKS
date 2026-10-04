/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CLOCK_FACE_H
#define UDEKS_CLOCK_FACE_H

/* User-space retained drawing model; not a resident graphics operation.
 * 24 face edges + 12 ticks + 2 hands + 5 doubled glyphs = 43 commands.
 * Initial migration uses a fixed 72x88 client under the existing GFX ABI. */
#define UDEKS_CLOCK_FACE_COMMANDS 43u
#define UDEKS_CLOCK_FACE_WIDTH 72u
#define UDEKS_CLOCK_FACE_HEIGHT 88u

unsigned char udeks_clock_face(unsigned char hour, unsigned char minute,
                             unsigned char *commands);
#endif
