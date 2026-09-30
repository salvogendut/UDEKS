/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private bank-1 service. No resident C runtime or KERNAL dependencies. */
#include "udeks/task_request.h"
#include "udeks/iec_slow.h"
#include "udeks/cbm_directory.h"

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
static struct udeks_cbm_directory directory;
static struct udeks_cbm_dir_entry entry;

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
    if (channel) udeks_iec_close();
    channel = 0;
}

static uint8_t io_error(void)
{
    close_channel();
    eof = 1u;
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
/* File policy stays in C. Read status channel 15 before attempting TALK 2,
 * so FILE NOT FOUND cannot turn into an indistinguishable data timeout. */
static uint8_t open_regular(uint8_t count)
{
    uint8_t i, c, attempt, status, code, ended;
    uint16_t value;
    if (count < 6u || count > 21u) return UDEKS_TREQ_EINVAL;
    udeks_iec_filename_length = count - 5u;
    for (i = 0; i < udeks_iec_filename_length; ++i) {
        c = P[i+5];
        if (c >= 'a' && c <= 'z') c -= 32;
        /* No DOS commands, wildcards, paths or write-mode suffix injection. */
        if (!((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
              c == ' ' || c == '.' || c == '-' || c == '_')) return UDEKS_TREQ_EINVAL;
        udeks_iec_filename[i] = c;
    }
    for (attempt = 0; attempt < 2u; ++attempt) {
        status = udeks_iec_prepare_file(device);
        if (status) { udeks_iec_close(); return UDEKS_TREQ_EIO; }
        status = udeks_iec_open_status();
        code = 0; ended = 0;
        if (!status) {
            for (i = 0; i < 64u; ++i) {
                value = udeks_iec_read_byte();
                if ((value >> 8) > UDEKS_IEC_EOI) break;
                c = value;
                if (i < 2u) {
                    if (c < '0' || c > '9') break;
                    code = code * 10u + c - '0';
                } else if (i == 2u && c != ',') break;
                if ((value >> 8) == UDEKS_IEC_EOI) { ended = i >= 3u; break; }
            }
        }
        status = udeks_iec_untalk();
        if (!ended || status) { udeks_iec_close(); return UDEKS_TREQ_EIO; }
        if (!code) {
            if (!udeks_iec_talk_file()) return 0;
            udeks_iec_close(); return UDEKS_TREQ_EIO;
        }
        status = udeks_iec_close();
        if (status || code != 62u) return UDEKS_TREQ_EIO;
        /* Commodore disks use two PETSCII uppercase alphabets. Retry the
         * alternate encoding only for DOS 62, never for an I/O failure. */
        for (i = 0; i < udeks_iec_filename_length; ++i) {
            c = udeks_iec_filename[i];
            if (c >= 'A' && c <= 'Z') udeks_iec_filename[i] = c + 0x80u;
        }
    }
    return UDEKS_TREQ_ENOENT;
}

static uint8_t read_regular(uint8_t count)
{
    uint8_t n = 0, status;
    uint16_t value;
    if (count > UDEKS_TASK_REQUEST_PAYLOAD_SIZE) return reply(UDEKS_TREQ_EINVAL, 0);
    if (!count) return reply(0, 0);
    if (read_error) return reply(UDEKS_TREQ_EIO, 0);
    if (eof) return reply(0, 0);
    while (n < count) {
        value = udeks_iec_read_byte();
        status = value >> 8;
        if (status > UDEKS_IEC_EOI) {
            read_error = 1; close_channel();
            return reply(n ? 0u : UDEKS_TREQ_EIO, n);
        }
        P[n++] = (uint8_t)value; /* The byte carrying EOI is part of the file. */
        if (status == UDEKS_IEC_EOI) {
            eof = 1;
            read_error = udeks_iec_close() != 0;
            channel = 0;
            break;
        }
    }
    return reply(0, n);
}
#ifdef __CC65__
#pragma code-name(pop)
#endif

uint8_t udeks_storage_dispatch(void)
{
    uint8_t op, count, fd, i, status, parsed;
    uint16_t value, budget;
    op = R[UDEKS_TREQ_OPERATION];
    count = R[UDEKS_TREQ_COUNT];
    fd = R[UDEKS_TREQ_DESCRIPTOR];
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
        status = udeks_iec_open_directory(P[0]);
        if (status) return reply(status == UDEKS_IEC_NO_DEVICE ? UDEKS_TREQ_ENODEV : UDEKS_TREQ_EIO, 0u);
        status = udeks_iec_close();
        if (status) return reply(UDEKS_TREQ_EIO, 0u);
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
            if (udeks_iec_open_directory(device)) return reply(UDEKS_TREQ_EIO, 0u);
            udeks_cbm_dir_init(&directory);
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
        status = channel ? udeks_iec_close() : UDEKS_IEC_OK;
        channel = opened = 0u;
        return reply(status ? UDEKS_TREQ_EIO : 0u, 0u);
    }
    if (op == UDEKS_TREQ_OP_READ)
        return regular ? read_regular(count) : reply(UDEKS_TREQ_EISDIR, 0u);
    if (regular) return reply(UDEKS_TREQ_ENOTDIR, 0u);
    /* Reject short buffers before consuming the stream. */
    if (count < 18u || count > UDEKS_TASK_REQUEST_PAYLOAD_SIZE)
        return reply(UDEKS_TREQ_EINVAL, 0u);
    if (eof) return reply(0u, 0u);
    for (budget = 0; budget < 256u; ++budget) {
        value = udeks_iec_read_byte();
        status = value >> 8;
        if (status > UDEKS_IEC_EOI) return io_error();
        parsed = udeks_cbm_dir_feed(&directory, (uint8_t)value, &entry);
        if (parsed == UDEKS_CBM_DIR_ERROR) return io_error();
        if (status == UDEKS_IEC_EOI || parsed == UDEKS_CBM_DIR_END) {
            if (udeks_cbm_dir_finish(&directory) != UDEKS_CBM_DIR_END) return io_error();
            close_channel();
            eof = 1u;
            return reply(0u, 0u);
        }
        if (parsed == UDEKS_CBM_DIR_ENTRY) {
            P[0] = UDEKS_DT_REG;
            P[1] = entry.name_length;
            for (i = 0; i < entry.name_length; ++i) {
                status = entry.name[i];
                /* DOS listings use either PETSCII alphabet; the console API
                 * takes ASCII. Case folding is presentation, not DOS naming. */
                if (status >= 0xc1u && status <= 0xdau) status -= 0x80u;
                P[i+2] = status;
            }
            return reply(0u, entry.name_length + 2u);
        }
    }
    return io_error();
}
