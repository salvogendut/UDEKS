/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/fs_namespace.h"
#include "udeks/task_request.h"

static uint8_t lower(uint8_t c)
{
    /* Both PETSCII alphabets in directory entries; requests use ASCII. */
    if (c >= 0xc1u && c <= 0xdau) c -= 0x80u;
    if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
    return c;
}

static uint8_t name_char(uint8_t c)
{
    return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
        c == '.' || c == '-' || c == '_' || c == ' ';
}

static uint8_t virtual_dir(const uint8_t *name, uint8_t length)
{
    if (length == 3u) {
        if (name[0] == 'b' && name[1] == 'i' && name[2] == 'n') return UDEKS_FS_BIN;
        if (name[0] == 'e' && name[1] == 't' && name[2] == 'c') return UDEKS_FS_ETC;
        if (name[0] == 'm' && name[1] == 'n' && name[2] == 't') return UDEKS_FS_MNT;
    }
    return UDEKS_FS_ROOT;
}

static uint8_t special_name(const uint8_t *name, uint8_t length)
{
    return name[0] == '.' && (length == 1u || (length == 2u && name[1] == '.'));
}

static uint8_t suffix_kind(const uint8_t *name, uint8_t n)
{
    if (n >= 3u && name[n-3u] == '.' && name[n-2u] == 's' && name[n-1u] == 'h')
        return UDEKS_FS_SCRIPT;
    if (n >= 4u && name[n-4u] == '.') {
        if (name[n-3u] == 'b' && name[n-2u] == 'i' && name[n-1u] == 'n')
            return UDEKS_FS_BINARY;
        if (name[n-3u] == 'e' && name[n-2u] == 't' && name[n-1u] == 'c')
            return UDEKS_FS_CONFIG;
    }
    return UDEKS_FS_RAW;
}

uint8_t udeks_fs_resolve(const uint8_t *path, uint8_t length, uint8_t cwd,
                        struct udeks_fs_path *out)
{
    struct udeks_fs_path candidate;
    uint8_t i, start, n, c, directory;
    if (!path || !out || cwd > UDEKS_FS_MNT || !length ||
        length > UDEKS_FS_PATH_MAX) return UDEKS_TREQ_EINVAL;
    candidate.directory = path[0] == '/' ? UDEKS_FS_ROOT : cwd;
    candidate.length = 0;
    for (i = 0; i <= UDEKS_FS_NAME_MAX; ++i) candidate.name[i] = 0;
    i = 0;
    while (i < length) {
        if (candidate.length) return UDEKS_TREQ_ENOTDIR;
        while (i < length && path[i] == '/') ++i;
        if (i == length) break;
        start = i;
        while (i < length && path[i] != '/') ++i;
        n = i - start;
        if (n > UDEKS_FS_NAME_MAX) return UDEKS_TREQ_EINVAL;
        if (path[start] == '.' && (n == 1u || (n == 2u && path[start+1u] == '.'))) {
            if (n == 2u) candidate.directory = UDEKS_FS_ROOT;
            continue;
        }
        for (n = 0; start < i; ++start, ++n) {
            if (path[start] >= 0x80u) return UDEKS_TREQ_EINVAL;
            c = lower(path[start]);
            if (!name_char(c)) return UDEKS_TREQ_EINVAL;
            candidate.name[n] = c;
        }
        directory = virtual_dir(candidate.name, n);
        if (candidate.directory == UDEKS_FS_ROOT && directory) {
            candidate.directory = directory;
            for (n = 0; n <= UDEKS_FS_NAME_MAX; ++n) candidate.name[n] = 0;
        } else candidate.length = n;
    }
    /* BIN's stricter stem limit is checked per physical candidate. */
    if ((candidate.directory == UDEKS_FS_BIN && candidate.length > 13u) ||
        (candidate.directory == UDEKS_FS_ETC && candidate.length > 12u))
        return UDEKS_TREQ_EINVAL;
    *out = candidate;
    return 0;
}

uint8_t udeks_fs_device(const struct udeks_fs_volumes *volumes,
                       uint8_t directory, uint8_t *device)
{
    uint8_t unit;
    if (!volumes || !device || directory > UDEKS_FS_MNT) return UDEKS_TREQ_EINVAL;
    unit = directory == UDEKS_FS_MNT ? volumes->data : volumes->root;
    if (!unit) return UDEKS_TREQ_ENODEV;
    if (unit < 8u || unit > 11u) return UDEKS_TREQ_EINVAL;
    *device = unit;
    return 0;
}

uint8_t udeks_fs_classify(const uint8_t *physical, uint8_t data_volume,
                         struct udeks_fs_path *out, uint8_t *kind)
{
    struct udeks_fs_path candidate;
    uint8_t i, c, k, n;
    if (!physical || !out || !kind || data_volume > 1u) return UDEKS_TREQ_EINVAL;
    candidate.directory = data_volume ? UDEKS_FS_MNT : UDEKS_FS_ROOT;
    candidate.length = 0;
    k = UDEKS_FS_RAW;
    for (i = 0; i < UDEKS_FS_NAME_MAX; ++i) {
        c = physical[i];
        if (c == 0xa0u) break;
        c = lower(c);
        if (!name_char(c)) return UDEKS_TREQ_EINVAL;
        candidate.name[i] = c;
        ++candidate.length;
    }
    /* Reject malformed padding rather than silently aliasing a prefix. */
    for (n = i; n < UDEKS_FS_NAME_MAX; ++n)
        if (physical[n] != 0xa0u) return UDEKS_TREQ_EINVAL;
    for (; i <= UDEKS_FS_NAME_MAX; ++i) candidate.name[i] = 0;
    n = candidate.length;
    if (!n) return UDEKS_TREQ_EINVAL;
    if (!data_volume) {
        k = suffix_kind(candidate.name, n);
        if (k != UDEKS_FS_RAW) {
            n -= k == UDEKS_FS_SCRIPT ? 3u : 4u;
            candidate.directory = k == UDEKS_FS_CONFIG ? UDEKS_FS_ETC : UDEKS_FS_BIN;
        }
    }
    if (!n || special_name(candidate.name, n)) return UDEKS_TREQ_EINVAL;
    if (candidate.directory == UDEKS_FS_ROOT && virtual_dir(candidate.name, n))
        return UDEKS_TREQ_EEXIST;
    candidate.length = n;
    for (; n <= UDEKS_FS_NAME_MAX; ++n) candidate.name[n] = 0;
    *out = candidate;
    *kind = k;
    return 0;
}

#ifndef UDEKS_FS_READ_ONLY
/* Outgoing filename generation is for a future write/create service. The
 * read-only runtime scans/classifies real directory entries instead. Keep
 * this host-tested contract, but do not deliver unused code to the C128. */
uint8_t udeks_fs_physical(const struct udeks_fs_path *path, uint8_t kind,
                         uint8_t *physical)
{
    uint8_t i, suffix_length, n, c;
    const uint8_t *suffix;
    if (!path || !physical || path->directory > UDEKS_FS_MNT || !path->length ||
        path->length > UDEKS_FS_NAME_MAX) return UDEKS_TREQ_EINVAL;
    suffix = (const uint8_t *)"";
    suffix_length = 0;
    switch (kind) {
        case UDEKS_FS_RAW:
            if (path->directory != UDEKS_FS_ROOT && path->directory != UDEKS_FS_MNT)
                return UDEKS_TREQ_EINVAL;
            break;
        case UDEKS_FS_BINARY:
        case UDEKS_FS_SCRIPT:
            if (path->directory != UDEKS_FS_BIN) return UDEKS_TREQ_EINVAL;
            suffix = (const uint8_t *)(kind == UDEKS_FS_BINARY ? ".BIN" : ".SH");
            suffix_length = kind == UDEKS_FS_BINARY ? 4u : 3u;
            break;
        case UDEKS_FS_CONFIG:
            if (path->directory != UDEKS_FS_ETC) return UDEKS_TREQ_EINVAL;
            suffix = (const uint8_t *)".ETC";
            suffix_length = 4;
            break;
        default: return UDEKS_TREQ_EINVAL;
    }
    n = path->length;
    if (n + suffix_length > UDEKS_FS_NAME_MAX || path->name[n] ||
        special_name(path->name, n)) return UDEKS_TREQ_EINVAL;
    if (path->directory == UDEKS_FS_ROOT && virtual_dir(path->name, n))
        return UDEKS_TREQ_EEXIST;
    for (i = 0; i < n; ++i)
        if (!name_char(path->name[i])) return UDEKS_TREQ_EINVAL;
    /* A suffix-mapped system file has ONE logical path, not a raw root alias. */
    if (path->directory == UDEKS_FS_ROOT && suffix_kind(path->name, n) != UDEKS_FS_RAW)
        return UDEKS_TREQ_ENOENT;
    /* All validation precedes the first output write. */
    for (i = 0; i < n; ++i) {
        c = path->name[i];
        physical[i] = c >= 'a' && c <= 'z' ? c - ('a' - 'A') : c;
    }
    for (i = 0; i < suffix_length; ++i) { physical[n] = suffix[i]; ++n; }
    while (n < UDEKS_FS_NAME_MAX) { physical[n] = 0xa0u; ++n; }
    return 0;
}
#endif

uint8_t udeks_fs_consider(const struct udeks_fs_path *query,
                         const uint8_t *physical, uint8_t *selected)
{
    struct udeks_fs_path candidate;
    uint8_t kind, error, i;
    if (!query || !selected || !query->length || query->length > UDEKS_FS_NAME_MAX ||
        query->directory > UDEKS_FS_MNT || *selected > UDEKS_FS_CONFIG)
        return UDEKS_TREQ_EINVAL;
    if (query->name[query->length] || special_name(query->name, query->length))
        return UDEKS_TREQ_EINVAL;
    for (i = 0; i < query->length; ++i)
        if (!name_char(query->name[i])) return UDEKS_TREQ_EINVAL;
    error = udeks_fs_classify(physical, query->directory == UDEKS_FS_MNT, &candidate, &kind);
    if (error) return error;
    if (candidate.directory != query->directory || candidate.length != query->length)
        return UDEKS_TREQ_ENOENT;
    for (i = 0; i < query->length; ++i)
        if (candidate.name[i] != query->name[i]) return UDEKS_TREQ_ENOENT;
    if (*selected) return UDEKS_TREQ_EEXIST;
    *selected = kind;
    return 0;
}
