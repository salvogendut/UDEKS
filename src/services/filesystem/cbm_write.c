/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Drive-managed create-only byte streams. The assembly transport owns timing;
 * this C module owns validation, DOS status, and sticky failure semantics. */
#include "udeks/cbm_write.h"
#include "udeks/cbm_file.h"
#include "udeks/iec_slow.h"
#include "udeks/task_request.h"

uint8_t udeks_cbm_written, udeks_cbm_write_dos_error;
static uint8_t active, failed;
static uint8_t empty, created_device, created_name[16];

static uint8_t dos_errno(uint8_t code)
{
    switch (code) {
        case 0: return 0;
        case 26: return UDEKS_CBM_EROFS;
        case 60: case 70: return UDEKS_TREQ_EBUSY;
        case 62: return UDEKS_TREQ_ENOENT;
        case 63: return UDEKS_TREQ_EEXIST;
        case 72: return UDEKS_CBM_ENOSPC;
        case 74: return UDEKS_TREQ_ENODEV;
        default: return UDEKS_TREQ_EIO;
    }
}

/* Reading the error channel clears the drive's error, so retain the first
 * failure in the writer. Always UNTALK, including malformed/truncated replies.
 * A bounded reply must end in CR+EOI, not just look like a success prefix. */
static uint8_t status(void)
{
    uint8_t i, code = 0, bad = 0, complete = 0;
    uint16_t value;
    udeks_cbm_write_dos_error = 0;
    if (udeks_iec_open_status()) bad = 1;
    else for (i = 0; i < 64u; ++i) {
        value = udeks_iec_read_byte();
        if (value > 511u) break;
        if (i < 2u) {
            if ((uint8_t)value < '0' || (uint8_t)value > '9') bad = 1;
            else code = code * 10u + (uint8_t)value - '0';
        }
        if (i == 2u && (uint8_t)value != ',') bad = 1;
        if (value >= 256u) {
            complete = i >= 3u && (uint8_t)value == 13u;
            break;
        }
    }
    if (udeks_iec_untalk() || bad || !complete) return UDEKS_TREQ_EIO;
    udeks_cbm_write_dos_error = code;
    return dos_errno(code);
}

uint8_t udeks_cbm_create(uint8_t device, const uint8_t *name, uint8_t length)
{
    uint8_t i, c, error;
    if (active) return UDEKS_TREQ_EBUSY;
    if (device < 8u || device > 11u || !name || !length || length > 16u)
        return UDEKS_TREQ_EINVAL;
    if (name[0] == ' ' || name[length-1u] == ' ' ||
        (name[0] == '.' && (length == 1u || (length == 2u && name[1] == '.'))))
        return UDEKS_TREQ_EINVAL;
    for (i = 0; i < length; ++i) {
        c = name[i];
        if (!((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
              c == ' ' || c == '.' || c == '_' || c == '-')) return UDEKS_TREQ_EINVAL;
    }
    /* No transport call or shared filename mutation before full validation. */
    for (i = 0; i < 16u; ++i) created_name[i] = i < length ? name[i] : 0xa0u;
    created_device = device; empty = 1;
    udeks_iec_filename[0] = '0'; udeks_iec_filename[1] = ':';
    for (i = 0; i < length; ++i) udeks_iec_filename[i+2u] = name[i];
    udeks_iec_filename[i+2u] = ','; udeks_iec_filename[i+3u] = 'S';
    udeks_iec_filename[i+4u] = ','; udeks_iec_filename[i+5u] = 'W';
    udeks_iec_filename_length = length+6u;
    active = 1; failed = udeks_cbm_written = udeks_cbm_write_dos_error = 0;
    error = udeks_iec_prepare_file(device);
    if (error) failed = error == UDEKS_IEC_NO_DEVICE ? UDEKS_TREQ_ENODEV : UDEKS_TREQ_EIO;
    else failed = status();
    if (failed) return udeks_cbm_write_close();
    return 0;
}

uint8_t udeks_cbm_write(const uint8_t *data, uint8_t count)
{
    uint8_t error, dos;
    udeks_cbm_written = 0;
    if (!active) return UDEKS_TREQ_EBADF;
    if (count > UDEKS_CBM_WRITE_MAX || (count && !data)) return UDEKS_TREQ_EINVAL;
    if (failed) return failed;
    if (!count) return 0;
    empty = 0; /* even an uncertain transfer must never trigger empty repair */
    error = udeks_iec_listen_file();
    if (!error) while (udeks_cbm_written < count) {
        error = udeks_iec_write_byte((uint16_t)data[udeks_cbm_written] |
            (udeks_cbm_written == count-1u ? 256u : 0u));
        if (error) break;
        ++udeks_cbm_written;
    }
    if (udeks_iec_unlisten()) error = 1;
    dos = status();
    /* Prefer a concrete DOS error (e.g. disk full) to a subsequent timeout. */
    failed = dos ? dos : error ? UDEKS_TREQ_EIO : 0u;
    return failed;
}

uint8_t udeks_cbm_write_close(void)
{
    uint8_t error, dos;
    if (!active) return UDEKS_TREQ_EBADF;
    error = udeks_iec_close();
    /* CLOSE performs the final sector/BAM update; only now check its status.
     * open_status re-enters 1 MHz; finish restores the ORIGINAL caller speed. */
    dos = status();
    udeks_iec_finish();
    active = 0;
    if (failed) return failed;
    if (dos || error) return dos ? dos : UDEKS_TREQ_EIO;
    if (!empty) return 0;
    /* The read/direct-access transaction saves the original speed again.
     * Failed OPEN/WRITE/CLOSE never enters this path. No retry on failure. */
    /* The sector reader's raw diagnostic may contain stale or partial DOS
     * digits. Only its validated return code may become the caller's errno. */
    return udeks_cbm_finish_empty(created_device, created_name);
}
