/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private Commodore DOS directory-stream decoder; not a syscall ABI. */
#ifndef UDEKS_CBM_DIRECTORY_H
#define UDEKS_CBM_DIRECTORY_H
#include <stdint.h>

#define UDEKS_CBM_DIR_MORE  0u
#define UDEKS_CBM_DIR_ENTRY 1u
#define UDEKS_CBM_DIR_END   2u
#define UDEKS_CBM_DIR_ERROR 3u
#define UDEKS_CBM_DIR_NAME_MAX 16u
#define UDEKS_CBM_DIR_LINE_MAX 64u

struct udeks_cbm_dir_entry {
    uint16_t blocks;
    uint8_t name_length;
    uint8_t name[UDEKS_CBM_DIR_NAME_MAX]; /* raw PETSCII; no terminator */
    uint8_t type[3]; /* PRG, SEQ, USR, REL, DEL, etc. */
    uint8_t closed, locked;
};

/* The caller owns this state and may feed at most a bounded number of bytes
 * per service poll. A byte with ENTRY completes exactly one file record.
 * No pointers or transport state are retained here. */
struct udeks_cbm_directory {
    uint8_t phase, length, link_low, number_low, number_high;
    uint8_t saw_header, saw_footer;
    uint8_t line[UDEKS_CBM_DIR_LINE_MAX];
};

void udeks_cbm_dir_init(struct udeks_cbm_directory *directory);
uint8_t udeks_cbm_dir_feed(struct udeks_cbm_directory *directory,
                           uint8_t byte, struct udeks_cbm_dir_entry *entry);
/* Call only after the IEC transport reports EOI. */
uint8_t udeks_cbm_dir_finish(struct udeks_cbm_directory *directory);
/* Encode one parsed file into the existing explicit-byte GETDENTS payload.
 * Returns its length, or zero when the caller's payload is too small. */
uint8_t udeks_cbm_dir_encode(const struct udeks_cbm_dir_entry *entry,
                             uint8_t *payload, uint8_t capacity);
#endif
