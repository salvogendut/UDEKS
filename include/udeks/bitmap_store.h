/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_BITMAP_STORE_H
#define UDEKS_BITMAP_STORE_H
/* Private storage/reference interface; public wire contract: abi/window.md.
 * The boundary adapter must authenticate the task/window before selecting
 * index. Pool pointers never cross that boundary. Existing path/command
 * images share this exact pool and retain their length/format records.
 * All three format/state bits are excluded from physical byte lengths. */
#define UDEKS_BITMAP_POOL_BYTES 2304u
#define UDEKS_BITMAP_CLIENTS 4u
#define UDEKS_BITMAP_HEADER 8u
#define UDEKS_BITMAP_LENGTH 0x1fffu
#define UDEKS_BITMAP_PENDING 0x2000u
#define UDEKS_BITMAP_FORMAT 0x4000u
#define UDEKS_BITMAP_PATHS 0x8000u
#define UDEKS_BITMAP_BEGIN 8u
#define UDEKS_BITMAP_WRITE 9u
#define UDEKS_BITMAP_COMMIT 10u
#define UDEKS_BITMAP_ABORT 11u
#define UDEKS_BITMAP_CHUNK 19u

struct udeks_bitmap_store {
    unsigned char *pool;
    unsigned int *lengths; /* four service-owned records; zero means empty */
};

/* Serialized, binary-mode service calls, no yield/callback or file I/O.
 * index is 0..3; payload is a SNAPSHOT of the 24-byte graphics request.
 * Returns errno (0, EINVAL, ENOMEM, EBUSY). Rejection leaves all state intact.
 * BEGIN requires an empty image; this slice does not replace a live image.
 * P[1] is the window handle, checked by the future boundary adapter. */
unsigned char udeks_bitmap_request(struct udeks_bitmap_store *store,
    unsigned char index, const unsigned char *payload);
/* Borrow only until the next service call. NULL for absent/pending/nonbitmap.
 * Header: x LE16, y, width, height, stride, received LE16; then packed rows.
 * Pixels are MSB-first; unused low row bits are zero. */
const unsigned char *udeks_bitmap_view(struct udeks_bitmap_store *store,
    unsigned char index);
/* Owner retirement hook; supports bitmap, path and command records alike.
 * The boundary adapter MUST call it even if the owner has no visible image. */
void udeks_bitmap_discard(struct udeks_bitmap_store *store, unsigned char index);
#endif
