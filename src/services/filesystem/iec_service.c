/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Serialized bank-1 filesystem policy; no resident runtime or KERNAL calls. */
#include "udeks/task_request.h"
#include "udeks/iec_slow.h"
#include "udeks/cbm_file.h"
#include "udeks/fs_namespace.h"
#ifdef UDEKS_STORAGE_WRITES
#include "udeks/cbm_write.h"
#include "udeks/storage_write.h"
#endif
#ifdef UDEKS_STORAGE_MUTATIONS
#ifndef UDEKS_STORAGE_WRITES
#error "mutations require writable storage and trusted handle ownership"
#endif
#include "udeks/file_mutation.h"
#include "udeks/cbm_mutate.h"
#endif

#if defined(UDEKS_STORAGE_HOST_TEST) || defined(UDEKS_STORAGE_LEASE)
extern uint8_t udeks_storage_request[UDEKS_TASK_REQUEST_SIZE];
extern uint8_t udeks_storage_cwd, udeks_storage_boot_source;
#define R udeks_storage_request
#define CWD udeks_storage_cwd
#define BOOT_SOURCE udeks_storage_boot_source
#else
#define R ((volatile uint8_t *)UDEKS_TASK_REQUEST_BASE)
#define CWD (*(volatile uint8_t *)0xf2a6)
#define BOOT_SOURCE (*(volatile uint8_t *)0xf3dd)
#endif
#define P (R + UDEKS_TREQ_PAYLOAD)
#define FD 4u
#define O_DIRECTORY 1u

static struct udeks_fs_volumes volumes;
static struct udeks_fs_path query, entry;
static uint8_t opened, eof, channel, regular, read_error, device;
static uint8_t owner, directory, virtual_entry;
/* A 1581 directory has 296 slots, including deleted entries. */
static uint16_t next_entry;
static uint8_t selected, saved_entry[30];
#ifdef UDEKS_STORAGE_WRITES
static uint8_t writable, writing; /* permission bits: root=1, /mnt=2 */
static uint16_t handle_owner;
#endif
static const uint8_t * const directories[] = {
    (const uint8_t *)"/", (const uint8_t *)"/bin",
    (const uint8_t *)"/etc", (const uint8_t *)"/mnt"
};

#ifdef UDEKS_STORAGE_HOST_TEST
void udeks_storage_reset(void)
{
    volumes.root = volumes.data = 0;
    opened = eof = channel = regular = read_error = device = 0;
    owner = directory = next_entry = virtual_entry = 0;
    CWD = BOOT_SOURCE = 0;
#ifdef UDEKS_STORAGE_WRITES
    writable = writing = 0;
    handle_owner = 0;
#endif
}
#endif

static uint8_t reply(uint8_t error, uint8_t result)
{
    R[UDEKS_TREQ_ERROR] = error;
    R[UDEKS_TREQ_RESULT] = result;
    R[UDEKS_TREQ_STATE] = error ? UDEKS_TREQ_STATE_ERROR : UDEKS_TREQ_STATE_COMPLETE;
    return 1;
}

static void close_channel(void)
{
    if (channel) udeks_cbm_close();
    channel = 0;
}

#ifdef UDEKS_STORAGE_WRITES
static uint8_t close_handle(void)
{
    uint8_t error;
#ifdef UDEKS_STORAGE_MUTATIONS
    if (writing == 2u) {
        udeks_cbm_mutate_abort(); error = 0;
    } else
#endif
    if (writing) {
        error = udeks_cbm_write_close();
        if (read_error) error = read_error; /* preserve first WRITE failure */
    } else error = channel && udeks_cbm_close() ? UDEKS_TREQ_EIO : 0u;
    channel = opened = writing = 0;
    handle_owner = 0;
    return error;
}

uint8_t UDEKS_FASTCALL udeks_storage_cleanup(uint16_t instance)
{
    if (!opened || !instance || instance != handle_owner) return 0;
    return close_handle();
}
#endif

static uint8_t io_error(uint8_t error)
{
    close_channel();
    eof = 1; read_error = error;
    return reply(error, 0);
}

static uint8_t path(uint8_t count, uint8_t terminated)
{
    if (!count || count > UDEKS_FS_PATH_MAX || (terminated && P[count])) return UDEKS_TREQ_EINVAL;
    return udeks_fs_resolve((const uint8_t *)P, count, CWD, &query);
}

static uint8_t backing(uint8_t dir)
{
    uint8_t error = udeks_fs_device(&volumes, dir, &device);
    if (error == UDEKS_TREQ_ENODEV && R[UDEKS_TREQ_MINOR] < 8u)
        error = UDEKS_TREQ_ENOENT; /* old data-mount clients */
    return error;
}

/* A first match is provisional until EOF. Keep metadata, not an order winner.
 * Skip unaddressable names; collisions and transport errors invalidate lookup. */
static uint8_t find_unique(void)
{
    uint8_t status, error, i;
    selected = 0;
    if (udeks_cbm_begin(device)) return UDEKS_TREQ_EIO;
    error = 0;
    while ((status = udeks_cbm_next()) == 1u) {
        if (!(udeks_cbm_entry[0] & 0x3fu)) continue;
        error = udeks_fs_consider(&query, udeks_cbm_entry+3, &selected);
        if (error == UDEKS_TREQ_ENOENT || error == UDEKS_TREQ_EINVAL) { error = 0; continue; }
        if (error) break;
        for (i = 0; i < 30u; ++i) saved_entry[i] = udeks_cbm_entry[i];
    }
    if (status == 255u) error = UDEKS_TREQ_EIO;
    if (udeks_cbm_close()) error = UDEKS_TREQ_EIO;
    return error ? error : selected ? 0u : UDEKS_TREQ_ENOENT;
}

static uint8_t read_regular(uint8_t count)
{
    uint8_t n = 0;
    uint16_t value;
    if (count > UDEKS_TASK_REQUEST_PAYLOAD_SIZE) return reply(UDEKS_TREQ_EINVAL, 0);
    if (!count) return reply(0, 0);
    if (read_error) return reply(UDEKS_TREQ_EIO, 0);
    if (eof) return reply(0, 0);
    while (n < count) {
        value = udeks_cbm_read();
        if (value > 256u) {
            read_error = 1; close_channel();
            return reply(n ? 0u : UDEKS_TREQ_EIO, n);
        }
        if (value == 256u) {
            eof = 1;
            read_error = udeks_cbm_close() != 0;
            channel = 0;
            break;
        }
        /* Keep the store and increment separate: cc65 -Os/static-locals
         * otherwise hoists n++ ahead of this volatile indexed store. */
        P[n] = (uint8_t)value;
        ++n;
    }
    return reply(0, n);
}

/* A directory handle holds an index, not a live channel. Re-scan to validate
 * uniqueness without a resident filename index; STAT cannot disrupt a file. */
static uint8_t getdents(void)
{
    uint8_t status, error, kind, i, length;
    uint16_t index;
    if (directory == UDEKS_FS_ROOT && virtual_entry < 3u) {
        ++virtual_entry;
        P[0] = UDEKS_DT_DIR; P[1] = 3;
        for (i = 0; i < 3u; ++i) P[i+2] = directories[virtual_entry][i+1];
        return reply(0, 5);
    }
    if (backing(directory) || udeks_cbm_begin(device)) return io_error(UDEKS_TREQ_EIO);
    index = 0; error = 0;
    while ((status = udeks_cbm_next()) == 1u) {
        ++index;
        if (index <= next_entry || !(udeks_cbm_entry[0] & 0x3fu)) continue;
        error = udeks_fs_classify(udeks_cbm_entry+3, owner, &entry, &kind);
        if (error == UDEKS_TREQ_EINVAL) { error = 0; continue; }
        if (error) break;
        if (entry.directory != directory) continue;
        query = entry;
        break;
    }
    if (status == 255u) error = UDEKS_TREQ_EIO;
    if (udeks_cbm_close()) error = UDEKS_TREQ_EIO;
    if (error) return io_error(error);
    if (!status) { eof = 1; return reply(0, 0); }
    error = find_unique();
    if (error) return io_error(error);
    next_entry = index;
    length = query.length;
    P[0] = UDEKS_DT_REG; P[1] = length;
    for (i = 0; i < length; ++i) {
        kind = query.name[i];
        if (owner && kind >= 'a' && kind <= 'z') kind -= 32u;
        P[i+2] = kind; /* retain the old uppercase raw-data view */
    }
    return reply(0, length+2u);
}

#ifdef UDEKS_STORAGE_MUTATIONS
/* Reuses directory scratch; no extra filename allocation.
 * Wire/owner/path/permission rejection keeps the handle intact. Once those
 * checks pass, close_handle consumes it even if subsequent IO fails. */
#ifdef __CC65__
#pragma code-name(push, "STORAGEHIGH")
#endif
static uint8_t mutate(uint8_t op, uint8_t count, uint8_t fd)
{
    uint8_t error, kind, unit, empty, n;
    uint16_t value, caller;
    if (R[UDEKS_TREQ_MINOR] < UDEKS_FILE_MUTATION_MINOR)
        return UDEKS_TREQ_ENOSYS;
    caller = udeks_storage_caller();
    if (R[UDEKS_TREQ_FLAGS] == 1u) {
        if (count) return UDEKS_TREQ_EINVAL;
        if (fd != FD || !opened || !caller || caller != handle_owner ||
            writing != 2u || regular != op) return UDEKS_TREQ_EBADF;
        error = udeks_cbm_mutate_poll();
        goto mutation_result;
    }
    if (R[UDEKS_TREQ_FLAGS] || (op == UDEKS_FILE_UNLINK ? count != 0u :
        !count || count > UDEKS_FS_PATH_MAX || P[count])) return UDEKS_TREQ_EINVAL;
    if (fd != FD || !opened || !caller || caller != handle_owner || writing)
        return UDEKS_TREQ_EBADF;
    if (!regular) return UDEKS_TREQ_EISDIR;
    if (!(writable & (owner ? 2u : 1u))) return UDEKS_TREQ_EROFS;
    if (read_error) return UDEKS_TREQ_EIO;
    /* Reads may admit locked/USR files; destructive operations may not. */
    if (saved_entry[0] & 0x40u) return UDEKS_TREQ_EBUSY;
    if (saved_entry[0] != 0x81u && saved_entry[0] != 0x82u) return UDEKS_TREQ_EINVAL;
    n = 16;
    while (n && saved_entry[n+2u] == 0xa0u) --n;
    if (!n || saved_entry[3] == ' ' || saved_entry[n+2u] == ' ')
        return UDEKS_TREQ_EINVAL;
    /* OPEN/STAT/CHDIR attempts can overwrite query/device even while a
     * regular descriptor is live. Derive identity from its saved directory. */
    error = backing(directory);
    if (error) return error;
    if (op != UDEKS_FILE_UNLINK) {
        error = path(count, 1);
        if (error) return error;
        if (!query.length) return UDEKS_TREQ_EISDIR;
        error = udeks_fs_device(&volumes, query.directory, &unit);
        if (error) return error;
        if (unit != device || (query.directory == UDEKS_FS_MNT) != owner)
            return UDEKS_FILE_EXDEV;
        if (query.name[0] == ' ' || query.name[query.length-1u] == ' ')
            return UDEKS_TREQ_EINVAL;
        error = udeks_fs_classify(saved_entry+3, owner, &entry, &kind);
        if (error) return error;
        kind = query.directory == UDEKS_FS_BIN ?
            (kind == UDEKS_FS_SCRIPT ? UDEKS_FS_SCRIPT : UDEKS_FS_BINARY) :
            query.directory == UDEKS_FS_ETC ? UDEKS_FS_CONFIG : UDEKS_FS_RAW;
        error = udeks_fs_physical(&query, kind, entry.name);
        if (error) return error;
    }
    error = close_handle();
    if (error) return error;
    empty = 0;
    if (op == UDEKS_FILE_COPY) {
        /* Reopen from byte zero: EOF on an already-read descriptor is NOT
         * proof that the source was empty. The real sector reader verifies
         * its chain/link before reporting EOF. Always check this close too. */
        if (udeks_cbm_begin(device)) return UDEKS_TREQ_EIO;
        for (n = 0; n < 30u; ++n) udeks_cbm_entry[n] = saved_entry[n];
        error = udeks_cbm_select();
        if (!error) {
            value = udeks_cbm_read();
            if (value > 256u) error = UDEKS_TREQ_EIO;
            empty = value == 256u;
        }
        if (udeks_cbm_close()) error = UDEKS_TREQ_EIO;
        if (error) return error;
    }
    if (op != UDEKS_FILE_UNLINK) {
        /* Only a complete scan with NO match preserves saved_entry (source)
         * and authorizes the destination held in entry.name. */
        error = find_unique();
        if (error != UDEKS_TREQ_ENOENT) return error ? error : UDEKS_TREQ_EEXIST;
    }
    if (op == UDEKS_FILE_COPY) {
        error = udeks_cbm_space(device);
        if (error) return error;
        if (!udeks_cbm_free_blocks) return UDEKS_TREQ_ENOSPC;
        if (empty) {
            n = 0;
            while (n < 16u && entry.name[n] != 0xa0u) ++n;
            error = udeks_cbm_create(device, entry.name, n, saved_entry[0] & 3u);
            return error ? error : udeks_cbm_write_close();
        }
    }
    error = udeks_cbm_mutate(device, op - UDEKS_FILE_RENAME + UDEKS_CBM_RENAME,
        saved_entry+3, op == UDEKS_FILE_UNLINK ? 0 : entry.name);
mutation_result:
    if (error == UDEKS_TREQ_EAGAIN) {
        opened = 1; writing = 2; regular = op; handle_owner = caller;
    } else { opened = writing = 0; handle_owner = 0; }
    return error;
}
#ifdef __CC65__
#pragma code-name(pop)
#endif
#endif

uint8_t udeks_storage_dispatch(void)
{
    uint8_t op, count, fd, i, status, unit, root;
#ifdef UDEKS_STORAGE_WRITES
    uint8_t flags, bit, other;
    uint16_t caller;
    flags = R[UDEKS_TREQ_FLAGS];
#endif
    op = R[UDEKS_TREQ_OPERATION]; count = R[UDEKS_TREQ_COUNT]; fd = R[UDEKS_TREQ_DESCRIPTOR];
#ifdef UDEKS_STORAGE_MUTATIONS
    if (op >= UDEKS_FILE_RENAME && op <= UDEKS_FILE_UNLINK) {
        status = mutate(op, count, fd);
        return status == UDEKS_TREQ_EAGAIN ? reply(0, 1) : reply(status, 0);
    }
#endif
    if (op == UDEKS_TREQ_OP_MOUNT || op == UDEKS_TREQ_OP_UMOUNT) {
        if (R[UDEKS_TREQ_MINOR] < 5u) return reply(UDEKS_TREQ_ENOSYS, 0);
        i = op == UDEKS_TREQ_OP_MOUNT ? 1u : 0u;
#ifdef UDEKS_STORAGE_WRITES
        if (fd || (flags && (R[UDEKS_TREQ_MINOR] < UDEKS_STORAGE_WRITE_MINOR || !i)) ||
            (flags & ~(UDEKS_STORAGE_MOUNT_RW | UDEKS_STORAGE_MOUNT_REMOUNT)))
            return reply(UDEKS_TREQ_EINVAL, 0);
#else
        if (R[UDEKS_TREQ_FLAGS] || fd) return reply(UDEKS_TREQ_EINVAL, 0);
#endif
        root = count == i+1u && P[i] == '/';
        if (!root && (count != i+4u || P[i] != '/' || P[i+1] != 'm' ||
                      P[i+2] != 'n' || P[i+3] != 't')) return reply(UDEKS_TREQ_EINVAL, 0);
#ifdef UDEKS_STORAGE_WRITES
        bit = root ? 1u : 2u;
        if (root && (R[UDEKS_TREQ_MINOR] < 8u ||
            (BOOT_SOURCE && !(flags & UDEKS_STORAGE_MOUNT_REMOUNT))))
            return reply(UDEKS_TREQ_EBUSY, 0);
#else
        if (root && (R[UDEKS_TREQ_MINOR] < 8u || BOOT_SOURCE)) return reply(UDEKS_TREQ_EBUSY, 0);
#endif
        if (!i) {
            if (!(root ? volumes.root : volumes.data)) return reply(UDEKS_TREQ_ENOENT, 0);
            if ((opened && owner == !root) || (!root && CWD == UDEKS_FS_MNT))
                return reply(UDEKS_TREQ_EBUSY, 0);
            if (root) volumes.root = 0; else volumes.data = 0;
#ifdef UDEKS_STORAGE_WRITES
            writable &= ~bit;
#endif
            return reply(0, 0);
        }
        unit = P[0];
        if (unit < 8u || unit > 11u) return reply(UDEKS_TREQ_EINVAL, 0);
#ifdef UDEKS_STORAGE_WRITES
        if (opened) return reply(UDEKS_TREQ_EBUSY, 0);
        other = root ? volumes.data : volumes.root;
        /* Even a read-only alias of an already-writable device is misleading.
         * Two legacy read-only aliases remain allowed; neither can turn RW. */
        if (other == unit && ((flags & UDEKS_STORAGE_MOUNT_RW) || (writable & (3u ^ bit))))
            return reply(UDEKS_TREQ_EBUSY, 0);
        if (flags & UDEKS_STORAGE_MOUNT_REMOUNT) {
            other = root ? volumes.root : volumes.data;
            if (!other) return reply(UDEKS_TREQ_ENODEV, 0);
            if (unit != other) return reply(UDEKS_TREQ_EINVAL, 0);
            writable &= ~bit;
            if (flags & UDEKS_STORAGE_MOUNT_RW) writable |= bit;
            return reply(0, 0); /* permission only; no disk probe or cwd reset */
        }
#endif
        if (opened || (root ? volumes.root : volumes.data)) return reply(UDEKS_TREQ_EBUSY, 0);
        status = udeks_cbm_begin(unit);
        if (status) return reply(status == UDEKS_IEC_NO_DEVICE ? UDEKS_TREQ_ENODEV : UDEKS_TREQ_EIO, 0);
        status = udeks_cbm_next(); i = udeks_cbm_close();
        if (status != 1u || i) return reply(UDEKS_TREQ_EIO, 0);
        if (root) { volumes.root = unit; CWD = UDEKS_FS_ROOT; }
        else volumes.data = unit;
#ifdef UDEKS_STORAGE_WRITES
        writable &= ~bit;
        if (flags & UDEKS_STORAGE_MOUNT_RW) writable |= bit;
#endif
        return reply(0, 0);
    }
    if (op == UDEKS_TREQ_OP_GETCWD) {
        if (R[UDEKS_TREQ_MINOR] < 8u) return reply(UDEKS_TREQ_ENOSYS, 0);
        if (fd || count || R[UDEKS_TREQ_FLAGS] || CWD > UDEKS_FS_MNT)
            return reply(UDEKS_TREQ_EINVAL, 0);
        i = 0;
        do { P[i] = directories[CWD][i]; if (!P[i]) break; ++i; } while (1);
        return reply(0, i);
    }
    if (op == UDEKS_TREQ_OP_CHDIR || op == UDEKS_TREQ_OP_STATFS ||
        op == UDEKS_TREQ_OP_OPEN || op == UDEKS_TREQ_OP_STAT) {
        if ((op == UDEKS_TREQ_OP_CHDIR && R[UDEKS_TREQ_MINOR] < 8u) ||
            (op == UDEKS_TREQ_OP_STATFS && R[UDEKS_TREQ_MINOR] < 6u))
            return reply(UDEKS_TREQ_ENOSYS, 0);
        if (R[UDEKS_TREQ_FLAGS] || (op != UDEKS_TREQ_OP_OPEN && fd) ||
            fd > (
#ifdef UDEKS_STORAGE_WRITES
                R[UDEKS_TREQ_MINOR] >= 16u ? UDEKS_TREQ_OPEN_CREATE_PRG :
                R[UDEKS_TREQ_MINOR] >= UDEKS_STORAGE_WRITE_MINOR ? UDEKS_STORAGE_OPEN_CREATE :
#endif
                R[UDEKS_TREQ_MINOR] >= 8u ? UDEKS_TREQ_OPEN_EXEC : O_DIRECTORY))
            return reply(UDEKS_TREQ_EINVAL, 0);
        status = path(count, op != UDEKS_TREQ_OP_STATFS);
        if (status) return reply(status, 0);
        if (op == UDEKS_TREQ_OP_STATFS && query.length) return reply(UDEKS_TREQ_EINVAL, 0);
#ifdef UDEKS_STORAGE_WRITES
        if (op == UDEKS_TREQ_OP_OPEN && fd >= UDEKS_STORAGE_OPEN_CREATE &&
            !volumes.root && query.directory != UDEKS_FS_MNT)
            return reply(UDEKS_CBM_EROFS, 0); /* recovery bootfs cannot create */
#endif
        if (!volumes.root && query.directory != UDEKS_FS_MNT &&
            (op == UDEKS_TREQ_OP_OPEN || op == UDEKS_TREQ_OP_STAT)) return 0;
        if (op == UDEKS_TREQ_OP_CHDIR && !volumes.root && !query.length &&
            query.directory <= UDEKS_FS_BIN) { CWD = query.directory; return reply(0, 0); }
        status = backing(query.directory);
        if (status) return reply(status, 0);
        if (op == UDEKS_TREQ_OP_STATFS) {
            if (opened) return reply(UDEKS_TREQ_EBUSY, 0);
            status = udeks_cbm_space(device);
            if (status) return reply(status, 0);
            P[0] = 0; P[1] = 1;
            P[2] = udeks_cbm_total_blocks; P[3] = udeks_cbm_total_blocks >> 8;
            P[4] = udeks_cbm_free_blocks; P[5] = udeks_cbm_free_blocks >> 8;
            P[6] = device; P[7] = UDEKS_STATFS_READ_ONLY;
#ifdef UDEKS_STORAGE_WRITES
            if (writable & (query.directory == UDEKS_FS_MNT ? 2u : 1u)) P[7] = 0;
#endif
            return reply(0, UDEKS_STATFS_SIZE);
        }
        if (op == UDEKS_TREQ_OP_STAT) {
            if (query.length) return reply(UDEKS_TREQ_ENOSYS, 0);
            P[0] = UDEKS_DT_DIR; P[1] = P[2] = 0;
            return reply(0, UDEKS_STAT_SIZE);
        }
        if (op == UDEKS_TREQ_OP_CHDIR) {
            if (query.length) {
                if (opened) return reply(UDEKS_TREQ_EBUSY, 0);
                status = find_unique();
                return reply(status ? status : UDEKS_TREQ_ENOTDIR, 0);
            }
            CWD = query.directory;
            return reply(0, 0);
        }
        if (opened) return reply(UDEKS_TREQ_EMFILE, 0);
#ifdef UDEKS_STORAGE_WRITES
        caller = udeks_storage_caller();
        if (!caller) return reply(UDEKS_TREQ_ESRCH, 0);
        if (fd >= UDEKS_STORAGE_OPEN_CREATE) {
            if (!query.length) return reply(UDEKS_TREQ_EISDIR, 0);
            if (!(writable & (query.directory == UDEKS_FS_MNT ? 2u : 1u)))
                return reply(UDEKS_CBM_EROFS, 0);
            /* First milestone: ordinary data only. No executable/config
             * installer or ambiguous BIN/SH create policy. Validate before IO. */
            if (query.name[0] == ' ' || query.name[query.length-1u] == ' ')
                return reply(UDEKS_TREQ_EINVAL, 0);
            status = udeks_fs_physical(&query, UDEKS_FS_RAW, saved_entry);
            if (status) return reply(status, 0);
            status = find_unique();
            if (status != UDEKS_TREQ_ENOENT)
                return reply(status ? status : UDEKS_TREQ_EEXIST, 0);
            /* A completely full DOS image can fail allocation with a track
             * error instead of DOS 72. Reject known exhaustion before OPEN;
             * never reinterpret a real transport/geometry error as ENOSPC.
             * Even an empty SEQ needs one data block. */
            status = udeks_cbm_space(device);
            if (status) return reply(status, 0);
            if (!udeks_cbm_free_blocks) return reply(UDEKS_CBM_ENOSPC, 0);
            /* find_unique writes saved_entry only on a match. No-match leaves
             * the validated physical name intact; every other result rejects. */
            i = 0;
            while (i < 16u && saved_entry[i] != 0xa0u) ++i;
            status = udeks_cbm_create(device, saved_entry, i,
                fd == UDEKS_TREQ_OPEN_CREATE_PRG ? 2u : 1u);
            if (status) return reply(status, 0);
            writing = 1;
            channel = 0;
        } else {
            writing = 0;
#endif
        if (query.length) {
            if (fd == O_DIRECTORY) return reply(UDEKS_TREQ_ENOTDIR, 0);
            status = find_unique();
            if (status) return reply(status, 0);
            if (fd == UDEKS_TREQ_OPEN_EXEC && (selected == UDEKS_FS_SCRIPT || selected == UDEKS_FS_CONFIG))
                return reply(UDEKS_TREQ_ENOEXEC, 0);
            if (udeks_cbm_begin(device)) return reply(UDEKS_TREQ_EIO, 0);
            for (i = 0; i < 30u; ++i) udeks_cbm_entry[i] = saved_entry[i];
            status = udeks_cbm_select();
            if (status) { udeks_cbm_close(); return reply(status, 0); }
            channel = 1;
        } else if (fd == UDEKS_TREQ_OPEN_EXEC) return reply(UDEKS_TREQ_EISDIR, 0);
#ifdef UDEKS_STORAGE_WRITES
        }
        handle_owner = caller;
#endif
        regular = query.length != 0;
        directory = query.directory;
        owner = directory == UDEKS_FS_MNT;
        opened = 1; eof = read_error = next_entry = virtual_entry = 0;
        return reply(0, FD);
    }
    if (op == UDEKS_TREQ_OP_READ && fd != FD) return reply(UDEKS_TREQ_EBADF, 0);
#ifdef UDEKS_STORAGE_WRITES
    if (op == UDEKS_TREQ_OP_WRITE) {
        if (fd == 1u || fd == 2u) return 0; /* console routing is unchanged */
        if (fd != FD || R[UDEKS_TREQ_MINOR] < UDEKS_STORAGE_WRITE_MINOR)
            return reply(UDEKS_TREQ_EBADF, 0);
    }
#endif
    if ((op != UDEKS_TREQ_OP_GETDENTS && op != UDEKS_TREQ_OP_CLOSE &&
#ifdef UDEKS_STORAGE_WRITES
         op != UDEKS_TREQ_OP_WRITE &&
#endif
         op != UDEKS_TREQ_OP_READ) || fd != FD) return 0;
    if (!opened) return reply(UDEKS_TREQ_EBADF, 0);
#ifdef UDEKS_STORAGE_WRITES
    caller = udeks_storage_caller();
    if (!caller || caller != handle_owner) return reply(UDEKS_TREQ_EBADF, 0);
#endif
    if (R[UDEKS_TREQ_FLAGS]) return reply(UDEKS_TREQ_EINVAL, 0);
    if (op == UDEKS_TREQ_OP_CLOSE) {
        if (count) return reply(UDEKS_TREQ_EINVAL, 0);
#ifdef UDEKS_STORAGE_WRITES
        return reply(close_handle(), 0);
#else
        status = channel ? udeks_cbm_close() : UDEKS_IEC_OK;
        channel = opened = 0;
        return reply(status ? UDEKS_TREQ_EIO : 0, 0);
#endif
    }
#ifdef UDEKS_STORAGE_WRITES
    if (writing == 2u) return reply(UDEKS_TREQ_EBUSY, 0);
    if (op == UDEKS_TREQ_OP_WRITE) {
        if (!writing) return reply(UDEKS_TREQ_EBADF, 0);
        if (count > UDEKS_CBM_WRITE_MAX) return reply(UDEKS_TREQ_EINVAL, 0);
        if (read_error) return reply(read_error, 0);
        read_error = udeks_cbm_write((const uint8_t *)P, count);
        /* Return an accepted prefix once, then the sticky failure. CLOSE also
         * reports it even if this chunk acknowledged every byte before error. */
        return reply(udeks_cbm_written ? 0u : read_error, udeks_cbm_written);
    }
    if (writing) return reply(op == UDEKS_TREQ_OP_READ ? UDEKS_TREQ_EBADF : UDEKS_TREQ_ENOTDIR, 0);
#endif
    if (op == UDEKS_TREQ_OP_READ) return regular ? read_regular(count) : reply(UDEKS_TREQ_EISDIR, 0);
    if (regular) return reply(UDEKS_TREQ_ENOTDIR, 0);
    if (count < 18u || count > UDEKS_TASK_REQUEST_PAYLOAD_SIZE) return reply(UDEKS_TREQ_EINVAL, 0);
    if (read_error) return reply(read_error, 0);
    if (eof) return reply(0, 0);
    return getdents();
}
