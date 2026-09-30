/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Serialized bank-1 filesystem policy; no resident runtime or KERNAL calls. */
#include "udeks/task_request.h"
#include "udeks/iec_slow.h"
#include "udeks/cbm_file.h"
#include "udeks/fs_namespace.h"

#ifdef UDEKS_STORAGE_HOST_TEST
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
static uint8_t owner, directory, next_entry, virtual_entry;
static uint8_t selected, saved_entry[30];
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
        P[n++] = (uint8_t)value;
    }
    return reply(0, n);
}

/* A directory handle holds an index, not a live channel. Re-scan to validate
 * uniqueness without a resident filename index; STAT cannot disrupt a file. */
static uint8_t getdents(void)
{
    uint8_t status, error, index, kind, i, length;
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

uint8_t udeks_storage_dispatch(void)
{
    uint8_t op, count, fd, i, status, unit, root;
    op = R[UDEKS_TREQ_OPERATION]; count = R[UDEKS_TREQ_COUNT]; fd = R[UDEKS_TREQ_DESCRIPTOR];
    if (op == UDEKS_TREQ_OP_MOUNT || op == UDEKS_TREQ_OP_UMOUNT) {
        if (R[UDEKS_TREQ_MINOR] < 5u) return reply(UDEKS_TREQ_ENOSYS, 0);
        i = op == UDEKS_TREQ_OP_MOUNT ? 1u : 0u;
        if (R[UDEKS_TREQ_FLAGS] || fd) return reply(UDEKS_TREQ_EINVAL, 0);
        root = count == i+1u && P[i] == '/';
        if (!root && (count != i+4u || P[i] != '/' || P[i+1] != 'm' ||
                      P[i+2] != 'n' || P[i+3] != 't')) return reply(UDEKS_TREQ_EINVAL, 0);
        if (root && (R[UDEKS_TREQ_MINOR] < 8u || BOOT_SOURCE)) return reply(UDEKS_TREQ_EBUSY, 0);
        if (!i) {
            if (!(root ? volumes.root : volumes.data)) return reply(UDEKS_TREQ_ENOENT, 0);
            if ((opened && owner == !root) || (!root && CWD == UDEKS_FS_MNT))
                return reply(UDEKS_TREQ_EBUSY, 0);
            if (root) volumes.root = 0; else volumes.data = 0;
            return reply(0, 0);
        }
        unit = P[0];
        if (unit < 8u || unit > 11u) return reply(UDEKS_TREQ_EINVAL, 0);
        if (opened || (root ? volumes.root : volumes.data)) return reply(UDEKS_TREQ_EBUSY, 0);
        status = udeks_cbm_begin(unit);
        if (status) return reply(status == UDEKS_IEC_NO_DEVICE ? UDEKS_TREQ_ENODEV : UDEKS_TREQ_EIO, 0);
        status = udeks_cbm_next(); i = udeks_cbm_close();
        if (status != 1u || i) return reply(UDEKS_TREQ_EIO, 0);
        if (root) { volumes.root = unit; CWD = UDEKS_FS_ROOT; }
        else volumes.data = unit;
        return reply(0, 0);
    }
    if (op == UDEKS_TREQ_OP_GETCWD) {
        if (R[UDEKS_TREQ_MINOR] < 8u) return reply(UDEKS_TREQ_ENOSYS, 0);
        if (fd || count || R[UDEKS_TREQ_FLAGS] || CWD > UDEKS_FS_MNT)
            return reply(UDEKS_TREQ_EINVAL, 0);
        i = 0;
        do { P[i] = directories[CWD][i]; } while (P[i++]);
        return reply(0, i-1u);
    }
    if (op == UDEKS_TREQ_OP_CHDIR || op == UDEKS_TREQ_OP_STATFS ||
        op == UDEKS_TREQ_OP_OPEN || op == UDEKS_TREQ_OP_STAT) {
        if ((op == UDEKS_TREQ_OP_CHDIR && R[UDEKS_TREQ_MINOR] < 8u) ||
            (op == UDEKS_TREQ_OP_STATFS && R[UDEKS_TREQ_MINOR] < 6u))
            return reply(UDEKS_TREQ_ENOSYS, 0);
        if (R[UDEKS_TREQ_FLAGS] || (op != UDEKS_TREQ_OP_OPEN && fd) ||
            fd > (R[UDEKS_TREQ_MINOR] >= 8u ? UDEKS_TREQ_OPEN_EXEC : O_DIRECTORY))
            return reply(UDEKS_TREQ_EINVAL, 0);
        status = path(count, op != UDEKS_TREQ_OP_STATFS);
        if (status) return reply(status, 0);
        if (op == UDEKS_TREQ_OP_STATFS && query.length) return reply(UDEKS_TREQ_EINVAL, 0);
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
        regular = query.length != 0;
        directory = query.directory;
        owner = directory == UDEKS_FS_MNT;
        opened = 1; eof = read_error = next_entry = virtual_entry = 0;
        return reply(0, FD);
    }
    if (op == UDEKS_TREQ_OP_READ && fd != FD) return reply(UDEKS_TREQ_EBADF, 0);
    if ((op != UDEKS_TREQ_OP_GETDENTS && op != UDEKS_TREQ_OP_CLOSE &&
         op != UDEKS_TREQ_OP_READ) || fd != FD) return 0;
    if (!opened) return reply(UDEKS_TREQ_EBADF, 0);
    if (R[UDEKS_TREQ_FLAGS]) return reply(UDEKS_TREQ_EINVAL, 0);
    if (op == UDEKS_TREQ_OP_CLOSE) {
        if (count) return reply(UDEKS_TREQ_EINVAL, 0);
        status = channel ? udeks_cbm_close() : UDEKS_IEC_OK;
        channel = opened = 0;
        return reply(status ? UDEKS_TREQ_EIO : 0, 0);
    }
    if (op == UDEKS_TREQ_OP_READ) return regular ? read_regular(count) : reply(UDEKS_TREQ_EISDIR, 0);
    if (regular) return reply(UDEKS_TREQ_ENOTDIR, 0);
    if (count < 18u || count > UDEKS_TASK_REQUEST_PAYLOAD_SIZE) return reply(UDEKS_TREQ_EINVAL, 0);
    if (read_error) return reply(read_error, 0);
    if (eof) return reply(0, 0);
    return getdents();
}
