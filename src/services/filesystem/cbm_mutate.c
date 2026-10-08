/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Exact-name drive-managed operations. Namespace/permissions belong to the
 * service; this backend cannot accept arbitrary DOS command strings. */
#include "udeks/cbm_mutate.h"
#include "udeks/iec_slow.h"
#include "udeks/task_request.h"

static uint8_t name_length(const uint8_t *name)
{
    uint8_t i, n = 16, c;
    if (!name) return 0;
    for (i = 0; i < 16u; ++i) {
        c = name[i];
        if (c == 0xa0u) { if (n == 16u) n = i; continue; }
        if (n != 16u) return 0;
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
              (c >= 0xc1u && c <= 0xdau) || (c >= '0' && c <= '9') ||
              c == ' ' || c == '.' || c == '_' || c == '-')) return 0;
    }
    if (!n || name[0] == ' ' || name[n-1u] == ' ' ||
        (name[0] == '.' && (n == 1u || (n == 2u && name[1] == '.')))) return 0;
    return n;
}

/* Full DOS status, including the scratch count. A valid 01 alone does not
 * prove that exactly one file was deleted. No response buffer or retry. */
static uint8_t result(uint8_t operation)
{
    uint8_t i, field = 0, digits = 0, number = 0, code = 0, count = 0;
    uint8_t c, error = UDEKS_TREQ_EIO, complete = 0;
    uint16_t value;
    c = udeks_iec_open_status();
#ifdef UDEKS_MUTATE_PROBE
    *(volatile uint8_t *)0x6011 = c;
    {
    extern uint8_t udeks_iec_probe_subphase, udeks_iec_probe_bus;
    extern uint8_t udeks_iec_probe_sent, udeks_iec_probe_lines;
    *(volatile uint8_t *)0x6019 = udeks_iec_probe_subphase;
    *(volatile uint8_t *)0x601a = udeks_iec_probe_bus;
    *(volatile uint8_t *)0x601b = udeks_iec_probe_sent;
    *(volatile uint8_t *)0x601c = udeks_iec_probe_lines;
    }
#endif
    if (c) goto done;
    for (i = 0; i < 64u; ++i) {
        value = udeks_iec_read_byte();
#ifdef UDEKS_MUTATE_PROBE
        ((volatile uint8_t *)0x6020)[i] = value;
        *(volatile uint8_t *)0x6012 = i+1u;
        *(volatile uint8_t *)0x6013 = value >> 8;
#endif
        if (value > 511u) break;
        c = (uint8_t)value;
        if (value >= 256u) {
            complete = field == 3u && digits == 2u && c == 13u;
            break;
        }
        if (field == 1u) {
            if (c == ',') {
                if (!digits) break;
                field = 2; digits = number = 0;
            } else {
                if (c < 32u) break;
                ++digits;
            }
        } else if (c == ',') {
            if (digits != 2u || field == 3u) break;
            if (!field) code = number; else count = number;
            ++field; digits = number = 0;
        } else {
            if (c < '0' || c > '9' || digits == 2u) break;
            number = number * 10u + c - '0'; ++digits;
        }
    }
    if (!complete) goto done;
    switch (code) {
        case 0: if (operation != UDEKS_CBM_REMOVE && !count && !number) error = 0; break;
        case 1: if (operation == UDEKS_CBM_REMOVE && !number) {
                    if (count == 1u) error = 0;
                    else if (!count) error = UDEKS_TREQ_ENOENT;
                } break;
        case 26: error = UDEKS_TREQ_EROFS; break;
        case 60: case 70: error = UDEKS_TREQ_EBUSY; break;
        case 62: error = UDEKS_TREQ_ENOENT; break;
        case 63: error = UDEKS_TREQ_EEXIST; break;
        case 72: error = UDEKS_TREQ_ENOSPC; break;
        case 74: error = UDEKS_TREQ_ENODEV; break;
    }
done:
    if (udeks_iec_untalk()) error = UDEKS_TREQ_EIO;
    return error;
}

uint8_t udeks_cbm_mutate(uint8_t device, uint8_t operation,
    const uint8_t *source, const uint8_t *destination)
{
    uint8_t n, m = 0, i, pos, error;
    if (device < 8u || device > 11u || operation < UDEKS_CBM_RENAME ||
        operation > UDEKS_CBM_REMOVE) return UDEKS_TREQ_EINVAL;
    n = name_length(source);
    if (!n) return UDEKS_TREQ_EINVAL;
    if (operation == UDEKS_CBM_REMOVE) {
        if (destination) return UDEKS_TREQ_EINVAL;
    } else {
        m = name_length(destination);
        if (!m) return UDEKS_TREQ_EINVAL;
        if (m == n) {
            for (i = 0; i < n && source[i] == destination[i]; ++i) {}
            if (i == n) return UDEKS_TREQ_EEXIST;
        }
    }
    /* Begin rejects a live transport without touching its filename or speed.
     * It opens no data channel and never sends CLOSE 15 to the drive. */
    error = udeks_iec_begin_command(device);
    if (error) return error == UDEKS_IEC_BAD_STATE ? UDEKS_TREQ_EBUSY : UDEKS_TREQ_EIO;
    udeks_iec_filename[0] = operation == UDEKS_CBM_REMOVE ? 'S' :
        operation == UDEKS_CBM_COPY ? 'C' : 'R';
    udeks_iec_filename[1] = '0'; udeks_iec_filename[2] = ':'; pos = 3;
    if (operation != UDEKS_CBM_REMOVE) {
        for (i = 0; i < m; ++i) { udeks_iec_filename[pos] = destination[i]; ++pos; }
        udeks_iec_filename[pos++] = '=';
        if (operation == UDEKS_CBM_COPY) {
            udeks_iec_filename[pos++] = '0'; udeks_iec_filename[pos++] = ':';
        }
    }
    for (i = 0; i < n; ++i) { udeks_iec_filename[pos] = source[i]; ++pos; }
    udeks_iec_filename_length = pos;
    error = udeks_iec_command();
#ifdef UDEKS_MUTATE_PROBE
    {
    extern uint8_t udeks_iec_probe_subphase, udeks_iec_probe_bus;
    extern uint8_t udeks_iec_probe_sent, udeks_iec_probe_eoi, udeks_iec_probe_defer;
    *(volatile uint8_t *)0x6010 = error;
    *(volatile uint8_t *)0x6014 = udeks_iec_probe_subphase;
    *(volatile uint8_t *)0x6015 = udeks_iec_probe_bus;
    *(volatile uint8_t *)0x6016 = udeks_iec_probe_sent;
    *(volatile uint8_t *)0x6017 = udeks_iec_probe_eoi;
    *(volatile uint8_t *)0x6018 = udeks_iec_probe_defer;
    }
#endif
    if (!error) error = result(operation);
    else {
        udeks_iec_unlisten(); /* terminate an uncertain partial command */
        error = error == UDEKS_IEC_NO_DEVICE ? UDEKS_TREQ_ENODEV : UDEKS_TREQ_EIO;
    }
    udeks_iec_finish();
    return error;
}
