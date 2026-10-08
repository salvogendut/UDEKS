/* SPDX-License-Identifier: GPL-3.0-or-later */
/* CBM-DOS sector-chain reader. U1 supplies all 256 bytes; the final sector's
 * link/count, not the serial stream's first-byte EOI, defines file length. */
#include "udeks/cbm_file.h"
#include "udeks/iec_slow.h"
#include "udeks/task_request.h"

uint8_t udeks_cbm_entry[30];
uint8_t udeks_cbm_dos_error;
static uint8_t active, talking, track, sector, remaining, slots, dirs;
static uint16_t blocks;
static uint8_t d81;

#ifdef __CC65__
#pragma code-name(push, "STORAGECODE")
#endif
static uint8_t sector_limit(uint8_t zone)
{
    if (d81) return 40;
    if (zone > 35u) zone -= 35u;
    if (zone <= 17u) return 21;
    if (zone <= 24u) return 19;
    if (zone <= 30u) return 18;
    return 17;
}
#ifdef __CC65__
#pragma code-name(pop)
#endif

#ifdef UDEKS_IEC_WRITE
static uint8_t read_sector(void);
static uint8_t untalk(void);
static uint8_t dos_status(void);
#if defined(__CC65__) && defined(UDEKS_STORAGE_HIGH)
#pragma code-name(push, "STORAGEHIGH")
#endif
/* Closed zero-data SEQ/PRG files acquire a CR in stock DOS. Correct ONLY the
 * length byte of the one block DOS just allocated to our new file. Its
 * buffer remains on the drive: U1 -> B-P -> one byte -> U2. The caller owns
 * the successful-create token; this is not exposed as truncate or raw I/O.
 * Scan to directory EOF before issuing any modifying command. */
uint8_t udeks_cbm_finish_empty(uint8_t device, const uint8_t *name)
{
    uint8_t i, state, found = 0, same, file_track = 0, file_sector = 0;
    uint8_t count, error = UDEKS_TREQ_EIO;
    uint16_t value;
    static const uint8_t pointer[] = "B-P:2 1";
    static const uint8_t update[] = "U2:2 0 00 00";
    if (udeks_cbm_begin(device)) return UDEKS_TREQ_EIO;
    while ((state = udeks_cbm_next()) == 1u) {
        if (!(udeks_cbm_entry[0] & 0x3fu)) continue;
        same = 1;
        for (i = 0; i < 16u; ++i) if (udeks_cbm_entry[i+3u] != name[i]) same = 0;
        if (!same) continue;
        if (found || (uint8_t)(udeks_cbm_entry[0] - 0x81u) > 1u ||
            udeks_cbm_entry[28] != 1u || udeks_cbm_entry[29]) goto done;
        found = 1;
        file_track = udeks_cbm_entry[1]; file_sector = udeks_cbm_entry[2];
    }
    if (state || !found || !file_track ||
        (d81 ? file_track == 40u : file_track == 18u || file_track == 53u)) goto done;
    /* Reject obvious cross-linked directory entries, including ones which
     * preceded our match. No other live entry may name this first sector. */
    track = d81 ? 40u : 18u; sector = d81 ? 3u : 1u;
    slots = 0; dirs = d81 ? 37u : 19u; found = 0;
    while ((state = udeks_cbm_next()) == 1u) {
        if ((udeks_cbm_entry[0] & 0x3fu) && udeks_cbm_entry[1] == file_track &&
            udeks_cbm_entry[2] == file_sector && ++found != 1u) goto done;
    }
    if (state || found != 1u) goto done;
    track = file_track; sector = file_sector;
    if (read_sector() || track || (sector != 1u && sector != 2u)) goto done;
    count = sector;
    value = udeks_iec_read_byte();
    if (value > 255u || (count == 2u && value != 13u)) goto done;
    /* Consume the entire U1 reply; a truncated/early-EOI sector isn't proof. */
    i = 3;
    do {
        value = udeks_iec_read_byte();
        if (value > 511u || (value > 255u && i != 255u)) goto done;
    } while (++i);
    if (value < 256u) goto done;
    if (count == 1u) { error = 0; goto done; } /* already exact-empty */
    if (untalk()) goto done;
    for (i = 0; i < 7u; ++i) udeks_iec_filename[i] = pointer[i];
    udeks_iec_filename_length = 7;
    if (udeks_iec_command() || dos_status()) goto done;
    state = udeks_iec_listen_file();
    if (!state) state = udeks_iec_write_byte(0x101u); /* position 1 := 1, EOI */
    if (udeks_iec_unlisten()) state = 1;
    if (dos_status() || state) goto done;
    for (i = 0; i < 12u; ++i) udeks_iec_filename[i] = update[i];
    udeks_iec_filename[7] += file_track / 10u;
    udeks_iec_filename[8] += file_track % 10u;
    udeks_iec_filename[10] += file_sector / 10u;
    udeks_iec_filename[11] += file_sector % 10u;
    udeks_iec_filename_length = 12;
    if (udeks_iec_command() || dos_status()) goto done;
    /* Re-read from disk, not the write buffer, and require the exact link. */
    track = file_track; sector = file_sector;
    if (read_sector() || track || sector != 1u || udeks_iec_read_byte() != 13u) goto done;
    error = 0;
done:
    if (udeks_cbm_close()) error = UDEKS_TREQ_EIO;
    return error;
}
#if defined(__CC65__) && defined(UDEKS_STORAGE_HIGH)
#pragma code-name(pop)
#endif
#endif

static uint8_t untalk(void)
{
    if (!talking) return 0;
    talking = 0;
    return udeks_iec_untalk();
}

uint8_t udeks_cbm_close(void)
{
    uint8_t status;
    status = active ? udeks_iec_close() : 0;
    active = talking = 0;
    return status;
}

/* Always consume and validate status before using a direct-access buffer:
 * a failed U1 must never expose the preceding sector as fresh data. */
static uint8_t dos_status(void)
{
    uint8_t i, bad = 0;
    uint16_t value;
    udeks_cbm_dos_error = 0;
    if (udeks_iec_open_status()) return 1;
    talking = 1;
    for (i = 0; i < 64u; ++i) {
        value = udeks_iec_read_byte();
        if (value > 511u) break;
        if (i < 2u) {
            if ((uint8_t)value < '0' || (uint8_t)value > '9') bad = 1;
            udeks_cbm_dos_error = udeks_cbm_dos_error * 10u + (uint8_t)value - '0';
        }
        if (i == 2u && (uint8_t)value != ',') bad = 1;
        if (value >= 256u) return untalk() || bad || udeks_cbm_dos_error || i < 3u;
    }
    return 1;
}

static uint8_t read_sector(void)
{
    static const uint8_t command[] = "U1:2 0 00 00";
    uint8_t i;
    uint16_t value;
    if (!track || track > (d81 ? 80u : 70u)) return 1;
    if (sector >= sector_limit(track) || untalk()) return 1;
    for (i = 0; i < 12u; ++i) udeks_iec_filename[i] = command[i];
    udeks_iec_filename[7] += track / 10u;
    udeks_iec_filename[8] += track % 10u;
    udeks_iec_filename[10] += sector / 10u;
    udeks_iec_filename[11] += sector % 10u;
    udeks_iec_filename_length = 12;
    if (udeks_iec_command() || dos_status() || udeks_iec_talk_file()) return 1;
    talking = 1;
    value = udeks_iec_read_byte();
    if (value > 255u) return 1;
    track = value;
    value = udeks_iec_read_byte();
    if (value > 255u) return 1;
    sector = value;
    return 0;
}

#ifdef __CC65__
#pragma code-name(push, "STORAGECODE")
#endif
uint8_t udeks_cbm_begin(uint8_t device)
{
    uint8_t status;
    udeks_iec_filename[0] = '#';
    udeks_iec_filename_length = 1;
    status = udeks_iec_prepare_file(device);
    if (status) { udeks_iec_close(); return status; }
    active = 1; talking = 0;
    slots = d81 = 0; dirs = 19;
    /* Read the volume header on EVERY open: device 8 and /mnt may use
     * different geometries, and removable media cannot be cached forever. */
    track = 18; sector = 0;
    if (!dos_status() && !read_sector() && udeks_iec_read_byte() == 0x41u &&
        track == 18u && sector == 1u) return 0;
    d81 = 1; track = 40; sector = 0; dirs = 37;
    if (!read_sector() && udeks_iec_read_byte() == 0x44u &&
        track == 40u && sector == 3u) return 0;
    udeks_cbm_close();
    return UDEKS_IEC_TIMEOUT;
}
#ifdef __CC65__
#pragma code-name(pop)
#endif

uint8_t udeks_cbm_next(void)
{
    uint8_t i;
    uint16_t value;
    if (!slots) {
        if (!track) return 0;
        if (track != (d81 ? 40u : 18u) || sector < (d81 ? 3u : 1u) || !dirs) return 255;
        --dirs;
        if (read_sector()) return 255;
        slots = 8;
    }
    for (i = 0; i < 30u; ++i) {
        value = udeks_iec_read_byte();
        if (value > 255u && !(value <= 511u && slots == 1u && i == 29u)) return 255;
        udeks_cbm_entry[i] = value;
    }
    if (--slots) {
        if (udeks_iec_read_byte() > 255u || udeks_iec_read_byte() > 255u) return 255;
    }
    return 1;
}

uint8_t udeks_cbm_select(void)
{
    uint8_t type = udeks_cbm_entry[0] & 0x3fu;
    if (!(udeks_cbm_entry[0] & 0x80u) || type < 1u || type > 3u)
        return UDEKS_TREQ_EINVAL; /* splat, REL and unsupported file types */
    track = udeks_cbm_entry[1]; sector = udeks_cbm_entry[2];
    blocks = udeks_cbm_entry[28] | ((uint16_t)udeks_cbm_entry[29] << 8);
    remaining = 0;
    if (blocks > (d81 ? 3200u : 1366u) || (!blocks != !track)) return UDEKS_TREQ_EIO;
    return 0;
}

uint16_t udeks_cbm_read(void)
{
    uint16_t value;
    if (!remaining) {
        if (!track) return blocks ? 512u : 256u;
        if (!blocks || read_sector()) return 512u;
        --blocks;
        if (track) {
            if (!blocks) return 512u;
            remaining = 254;
        } else {
            if (!sector || blocks) return 512u;
            remaining = sector - 1u;
            if (!remaining) return 256u;
        }
    }
    value = udeks_iec_read_byte();
    if (value > 511u || (value >= 256u && remaining != 1u)) return 512u;
    --remaining;
    return (uint8_t)value;
}

/* The first BAM holds free counts for both sides on a 1571. Stream it,
 * excluding the two directory tracks just as CBM DOS BLOCKS FREE does. */
uint16_t udeks_cbm_total_blocks, udeks_cbm_free_blocks;
#ifdef __CC65__
#ifdef UDEKS_STORAGE_HIGH
#pragma code-name(push, "STORAGECODE")
#else
#pragma code-name(push, "IECCODE")
#endif
#endif
uint8_t udeks_cbm_space(uint8_t device)
{
    uint8_t i, zone, bad, dual, page, next;
    uint16_t value;
    udeks_cbm_total_blocks = udeks_cbm_free_blocks = 0;
    if (udeks_cbm_begin(device)) return UDEKS_TREQ_EIO;
    page = d81 ? 1u : 0u;
again:
    track = d81 ? 40u : 18u; sector = page;
    bad = read_sector(); dual = 0;
    if (!bad) {
        i = 2; next = 16;
        do {
            value = udeks_iec_read_byte();
            if (value > 511u || (value > 255u && i != 255u)) { bad = 1; break; }
            if (i == 2u && (uint8_t)value != (d81 ? 0x44u : 0x41u)) bad = 1;
            if (i == 3u) dual = (uint8_t)value & 0x80u;
            zone = 0;
            if (d81) {
                if (i == 3u && (uint8_t)value != 0xbbu) bad = 1;
                if (i == next) {
                    next += 6;
                    if (page != 1u || i != 250u) zone = 1;
                }
            } else {
                if (i >= 4u && i <= 140u && !(i & 3u)) zone = i / 4u;
                if (dual && i >= 221u) zone = i - 220u;
            }
            if (zone) {
                if ((uint8_t)value > sector_limit(zone)) bad = 1;
                if (zone != 18u) udeks_cbm_free_blocks += (uint8_t)value;
            }
        } while (++i);
    }
    if (!bad && page == 1u) { ++page; goto again; }
    if (udeks_cbm_close()) bad = 1;
    if (bad) return UDEKS_TREQ_EIO;
    udeks_cbm_total_blocks = d81 ? 3160u : dual ? 1328u : 664u;
    return 0;
}
#ifdef __CC65__
#pragma code-name(pop)
#endif
