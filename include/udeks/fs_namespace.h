/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private C filesystem policy, NOT a wire/syscall ABI. */
#ifndef UDEKS_FS_NAMESPACE_H
#define UDEKS_FS_NAMESPACE_H
#include <stdint.h>

#define UDEKS_FS_PATH_MAX 23u
#define UDEKS_FS_NAME_MAX 16u
#define UDEKS_FS_DEFAULT_ROOT_DEVICE 8u
/* Preserve existing root-session cwd values for / and /bin. */
#define UDEKS_FS_ROOT 0u
#define UDEKS_FS_BIN  1u
#define UDEKS_FS_ETC  2u
#define UDEKS_FS_MNT  3u
#define UDEKS_FS_NONE   0u
#define UDEKS_FS_RAW    1u
#define UDEKS_FS_BINARY 2u
#define UDEKS_FS_SCRIPT 3u
#define UDEKS_FS_CONFIG 4u

struct udeks_fs_path {
    uint8_t directory;
    uint8_t length; /* zero denotes the directory itself */
    uint8_t name[UDEKS_FS_NAME_MAX + 1u]; /* folded ASCII, NUL terminated */
};
struct udeks_fs_volumes {
    uint8_t root; /* zero = unavailable, otherwise device 8..11 */
    uint8_t data; /* independent /mnt identity, not the system disk */
};

/* Bounded input, no terminator read. Resolves /, ., .. and repeated separators;
 * file/.. and file/ fail ENOTDIR, not lexical simplification. Success denotes
 * a candidate, NOT proof of existence. All outputs stay untouched on error. */
uint8_t udeks_fs_resolve(const uint8_t *path, uint8_t length, uint8_t cwd,
                        struct udeks_fs_path *out);
/* Missing mount -> ENODEV. NEVER fall back from system paths to /mnt. */
uint8_t udeks_fs_device(const struct udeks_fs_volumes *volumes,
                       uint8_t directory, uint8_t *device);
/* Exactly 16 raw CBM name bytes, A0 padded. System: BIN/SH -> /bin, ETC -> /etc,
 * otherwise /. Data: all names raw under /mnt. Physical root files cannot
 * shadow virtual directories. Caller validates file type/closed state/header. */
uint8_t udeks_fs_classify(const uint8_t *physical, uint8_t data_volume,
                         struct udeks_fs_path *out, uint8_t *kind);
/* Inverse translation for a specific kind. /bin lookup must consider BOTH
 * BIN and SH. Output is 16 A0-padded CBM bytes. No suffix on raw data names. */
uint8_t udeks_fs_physical(const struct udeks_fs_path *path, uint8_t kind,
                         uint8_t *physical);
/* Streaming lookup: selected starts at NONE. ENOENT = entry is not a match;
 * EEXIST = duplicate (including same-kind case-folded names). A first match
 * sets selected. Never return/load a file before the COMPLETE scan succeeds. */
uint8_t udeks_fs_consider(const struct udeks_fs_path *query,
                         const uint8_t *physical, uint8_t *selected);
#endif
