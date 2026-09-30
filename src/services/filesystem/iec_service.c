/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private bank-1 service. No resident C runtime or KERNAL dependencies. */
#include "udeks/task_request.h"
#include "udeks/iec_slow.h"
#include "udeks/cbm_file.h"

#ifdef UDEKS_STORAGE_HOST_TEST
extern uint8_t udeks_storage_request[UDEKS_TASK_REQUEST_SIZE];
#define R udeks_storage_request
#else
#define R ((volatile uint8_t *)UDEKS_TASK_REQUEST_BASE)
#endif
#define P (R + UDEKS_TREQ_PAYLOAD)
#define FD 4u
#define O_DIRECTORY 1u

static uint8_t mounted, opened, eof, channel, device;
static uint8_t regular, read_error;

#ifdef UDEKS_STORAGE_HOST_TEST
void udeks_storage_reset(void)
{
    mounted = opened = eof = channel = device = regular = read_error = 0u;
}
#endif

static uint8_t reply(uint8_t error, uint8_t result)
{
    R[UDEKS_TREQ_ERROR] = error;
    R[UDEKS_TREQ_RESULT] = result;
    R[UDEKS_TREQ_STATE] = error ? UDEKS_TREQ_STATE_ERROR : UDEKS_TREQ_STATE_COMPLETE;
    return 1u;
}

static void close_channel(void)
{
    if (channel) udeks_cbm_close();
    channel = 0;
}

static uint8_t io_error(void)
{
    close_channel();
    eof = 1u;
    read_error = 1u;
    return reply(UDEKS_TREQ_EIO, 0u);
}

/* Return 1 only for the exact mount or a child path, never /mnt-other. */
static uint8_t mount_path(uint8_t count)
{
    return count >= 4u && count < UDEKS_TASK_REQUEST_PAYLOAD_SIZE &&
        P[0] == '/' && P[1] == 'm' && P[2] == 'n' && P[3] == 't' &&
        (count == 4u || P[4] == '/');
}

#ifdef __CC65__
#pragma code-name(push, "CODE")
#endif
static uint8_t fold(uint8_t c)
{
    if (c >= 0xc1u && c <= 0xdau) return c - 0x80u;
    if (c >= 'a' && c <= 'z') return c - 32u;
    return c;
}

/* Directory lookup and byte-accurate sector chains are C service policy.
 * Both PETSCII uppercase alphabets map to the same ASCII spelling. */
static uint8_t open_regular(uint8_t count)
{
    uint8_t i, c, status, length;
    if (count < 6u || count > 21u) return UDEKS_TREQ_EINVAL;
    length = count - 5u;
    for (i = 0; i < length; ++i) {
        c = P[i+5];
        if (c >= 'a' && c <= 'z') c -= 32u;
        /* No DOS commands, wildcards, paths or write-mode suffix injection. */
        if (!((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
              c == ' ' || c == '.' || c == '-' || c == '_')) return UDEKS_TREQ_EINVAL;
    }
    if (udeks_cbm_begin(device)) return UDEKS_TREQ_EIO;
    while ((status = udeks_cbm_next()) == 1u) {
        if (!(udeks_cbm_entry[0] & 0x3fu)) continue;
        for (i = 0; i < length && fold(udeks_cbm_entry[i+3]) == fold(P[i+5]); ++i) {}
        if (i != length || (i < 16u && udeks_cbm_entry[i+3] != 0xa0u)) continue;
        status = udeks_cbm_select();
        if (!status) return 0;
        udeks_cbm_close();
        return status;
    }
    i = udeks_cbm_close();
    return status || i ? UDEKS_TREQ_EIO : UDEKS_TREQ_ENOENT;
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
#ifdef __CC65__
#pragma code-name(pop)
#endif

uint8_t udeks_storage_dispatch(void)
{
    uint8_t op, count, fd, i, status, length;
    op = R[UDEKS_TREQ_OPERATION];
    count = R[UDEKS_TREQ_COUNT];
    fd = R[UDEKS_TREQ_DESCRIPTOR];
    if (op == UDEKS_TREQ_OP_STATFS) {
        if (R[UDEKS_TREQ_MINOR] < 6u) return reply(UDEKS_TREQ_ENOSYS, 0);
        if (R[UDEKS_TREQ_FLAGS] || fd || count != 4u || !mount_path(count))
            return reply(UDEKS_TREQ_EINVAL, 0);
        if (!mounted) return reply(UDEKS_TREQ_ENOENT, 0);
        if (opened) return reply(UDEKS_TREQ_EBUSY, 0);
        status = udeks_cbm_space(device);
        if (status) return reply(status, 0);
        P[0] = 0; P[1] = 1;
        P[2] = udeks_cbm_total_blocks; P[3] = udeks_cbm_total_blocks >> 8;
        P[4] = udeks_cbm_free_blocks; P[5] = udeks_cbm_free_blocks >> 8;
        P[6] = device; P[7] = UDEKS_STATFS_READ_ONLY;
        return reply(0, UDEKS_STATFS_SIZE);
    }
    if (op == UDEKS_TREQ_OP_READ && fd != FD)
        return reply(UDEKS_TREQ_EBADF, 0u);
    if (op == UDEKS_TREQ_OP_MOUNT || op == UDEKS_TREQ_OP_UMOUNT) {
        if (R[UDEKS_TREQ_MINOR] < 5u) return reply(UDEKS_TREQ_ENOSYS, 0u);
        if (R[UDEKS_TREQ_FLAGS] || fd || count != (op == UDEKS_TREQ_OP_MOUNT ? 5u : 4u))
            return reply(UDEKS_TREQ_EINVAL, 0u);
        /* MOUNT payload: device, then four literal ASCII bytes /mnt. */
        i = op == UDEKS_TREQ_OP_MOUNT ? 1u : 0u;
        if (P[i] != '/' || P[i+1] != 'm' || P[i+2] != 'n' || P[i+3] != 't')
            return reply(UDEKS_TREQ_EINVAL, 0u);
        if (op == UDEKS_TREQ_OP_UMOUNT) {
            if (!mounted) return reply(UDEKS_TREQ_ENOENT, 0u);
            if (opened) return reply(UDEKS_TREQ_EBUSY, 0u);
            mounted = 0u;
            return reply(0u, 0u);
        }
        if (P[0] < 8u || P[0] > 11u) return reply(UDEKS_TREQ_EINVAL, 0u);
        if (mounted) return reply(UDEKS_TREQ_EBUSY, 0u);
        status = udeks_cbm_begin(P[0]);
        if (status) return reply(status == UDEKS_IEC_NO_DEVICE ? UDEKS_TREQ_ENODEV : UDEKS_TREQ_EIO, 0u);
        status = udeks_cbm_next(); /* actually read media, not only OPEN */
        i = udeks_cbm_close();
        if (status != 1u || i) return reply(UDEKS_TREQ_EIO, 0u);
        device = P[0];
        mounted = 1u;
        return reply(0u, 0u);
    }
    if (op == UDEKS_TREQ_OP_OPEN || op == UDEKS_TREQ_OP_STAT) {
        if (!mount_path(count)) return 0u; /* bootfs remains the fallback */
        if (R[UDEKS_TREQ_FLAGS] || P[count] || fd > O_DIRECTORY ||
            (op == UDEKS_TREQ_OP_STAT && fd)) return reply(UDEKS_TREQ_EINVAL, 0u);
        if (!mounted) return reply(UDEKS_TREQ_ENOENT, 0u);
        if (op == UDEKS_TREQ_OP_STAT) {
            if (count != 4u) return reply(UDEKS_TREQ_ENOSYS, 0u);
            P[0] = UDEKS_DT_DIR;
            P[1] = P[2] = 0u;
            return reply(0u, UDEKS_STAT_SIZE);
        }
        if (opened) return reply(UDEKS_TREQ_EMFILE, 0u);
        regular = count != 4u;
        if (regular) {
            if (fd == O_DIRECTORY) return reply(UDEKS_TREQ_ENOTDIR, 0);
            status = open_regular(count);
            if (status) return reply(status, 0);
        } else {
            if (udeks_cbm_begin(device)) return reply(UDEKS_TREQ_EIO, 0u);
        }
        channel = opened = 1u;
        eof = read_error = 0u;
        return reply(0u, FD);
    }
    if ((op != UDEKS_TREQ_OP_GETDENTS && op != UDEKS_TREQ_OP_CLOSE &&
         op != UDEKS_TREQ_OP_READ) || fd != FD) return 0u;
    if (!opened) return reply(UDEKS_TREQ_EBADF, 0u);
    if (R[UDEKS_TREQ_FLAGS]) return reply(UDEKS_TREQ_EINVAL, 0u);
    if (op == UDEKS_TREQ_OP_CLOSE) {
        if (count) return reply(UDEKS_TREQ_EINVAL, 0u);
        status = channel ? udeks_cbm_close() : UDEKS_IEC_OK;
        channel = opened = 0u;
        return reply(status ? UDEKS_TREQ_EIO : 0u, 0u);
    }
    if (op == UDEKS_TREQ_OP_READ)
        return regular ? read_regular(count) : reply(UDEKS_TREQ_EISDIR, 0u);
    if (regular) return reply(UDEKS_TREQ_ENOTDIR, 0u);
    /* Reject short buffers before consuming the stream. */
    if (count < 18u || count > UDEKS_TASK_REQUEST_PAYLOAD_SIZE)
        return reply(UDEKS_TREQ_EINVAL, 0u);
    if (read_error) return reply(UDEKS_TREQ_EIO, 0u);
    if (eof) return reply(0u, 0u);
    /* At most 19 directory sectors; malformed/cyclic chains cannot hang. */
    for (;;) {
        status = udeks_cbm_next();
        if (status == 255u) return io_error();
        if (!status) {
            status = udeks_cbm_close();
            channel = 0;
            if (status) return io_error();
            eof = 1u;
            return reply(0u, 0u);
        }
        if (!(udeks_cbm_entry[0] & 0x3fu)) continue;
        length = 16;
        while (length && udeks_cbm_entry[length+2] == 0xa0u) --length;
        if (!length) return io_error();
        P[0] = UDEKS_DT_REG; P[1] = length;
        for (i = 0; i < length; ++i) P[i+2] = fold(udeks_cbm_entry[i+3]);
        return reply(0u, length + 2u);
    }
}
