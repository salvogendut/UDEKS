/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/cbm_directory.h"
#include "udeks/task_request.h"

#define LOAD_LOW    0u
#define LOAD_HIGH   1u
#define LINK_LOW    2u
#define LINK_HIGH   3u
#define NUMBER_LOW  4u
#define NUMBER_HIGH 5u
#define BODY        6u
#define COMPLETE    7u
#define FAILED      8u

static uint8_t fail(struct udeks_cbm_directory *directory)
{
    directory->phase = FAILED;
    return UDEKS_CBM_DIR_ERROR;
}

static uint8_t footer(const uint8_t *line, uint8_t length)
{
    static const uint8_t marker[] = "BLOCKS FREE.";
    uint8_t i, j;
    for (i = 0; i != length && line[i] == ' '; ++i) {}
    if ((unsigned int)(length - i) < sizeof(marker) - 1u) return 0u;
    for (j = 0; j != sizeof(marker) - 1u &&
         line[i + j] == marker[j]; ++j) {}
    return j == sizeof(marker) - 1u;
}

static uint8_t complete_line(struct udeks_cbm_directory *directory,
                             struct udeks_cbm_dir_entry *entry)
{
    uint8_t first, last, end, position, length, i;
    const uint8_t *line = directory->line;

    if (!directory->saw_header) {
        if (directory->number_low || directory->number_high)
            return fail(directory);
        directory->saw_header = 1u;
        return UDEKS_CBM_DIR_MORE;
    }
    if (directory->saw_footer) return fail(directory);
    if (footer(line, directory->length)) {
        directory->saw_footer = 1u;
        return UDEKS_CBM_DIR_MORE;
    }
    for (first = 0; first != directory->length && line[first] != '"'; ++first) {}
    if (first == directory->length) return fail(directory);
    for (last = first + 1u; last != directory->length && line[last] != '"'; ++last) {}
    if (last == directory->length ||
        (unsigned int)(last - first) > UDEKS_CBM_DIR_NAME_MAX + 1u)
        return fail(directory);
    end = last;
    while (end > first + 1u && (line[end - 1u] == ' ' || line[end - 1u] == 0xA0u))
        --end;
    length = end - first - 1u;
    if (length == 0u) return fail(directory);
    position = last + 1u;
    while (position != directory->length && line[position] == ' ') ++position;
    entry->closed = 1u;
    if (position != directory->length && line[position] == '*') {
        entry->closed = 0u;
        ++position;
    }
    if (directory->length - position < 3) return fail(directory);
    entry->blocks = (uint16_t)directory->number_low |
        ((uint16_t)directory->number_high << 8);
    entry->name_length = length;
    for (i = 0; i != length; ++i) entry->name[i] = line[first + 1u + i];
    for (i = 0; i != 3u; ++i) entry->type[i] = line[position + i];
    entry->locked = position + 3u < directory->length &&
        line[position + 3u] == '<';
    return UDEKS_CBM_DIR_ENTRY;
}

void udeks_cbm_dir_init(struct udeks_cbm_directory *directory)
{
    if (!directory) return;
    directory->phase = LOAD_LOW;
    directory->length = directory->link_low = 0u;
    directory->number_low = directory->number_high = 0u;
    directory->saw_header = directory->saw_footer = 0u;
}

uint8_t udeks_cbm_dir_feed(struct udeks_cbm_directory *directory,
                           uint8_t byte, struct udeks_cbm_dir_entry *entry)
{
    uint8_t result;
    if (!directory || !entry) return UDEKS_CBM_DIR_ERROR;
    switch (directory->phase) {
    case LOAD_LOW:
        directory->phase = LOAD_HIGH;
        return UDEKS_CBM_DIR_MORE;
    case LOAD_HIGH:
        directory->phase = LINK_LOW;
        return UDEKS_CBM_DIR_MORE;
    case LINK_LOW:
        directory->link_low = byte;
        directory->phase = LINK_HIGH;
        return UDEKS_CBM_DIR_MORE;
    case LINK_HIGH:
        if (directory->link_low == 0u && byte == 0u) {
            if (!directory->saw_header || !directory->saw_footer)
                return fail(directory);
            directory->phase = COMPLETE;
            return UDEKS_CBM_DIR_END;
        }
        directory->phase = NUMBER_LOW;
        return UDEKS_CBM_DIR_MORE;
    case NUMBER_LOW:
        directory->number_low = byte;
        directory->phase = NUMBER_HIGH;
        return UDEKS_CBM_DIR_MORE;
    case NUMBER_HIGH:
        directory->number_high = byte;
        directory->length = 0u;
        directory->phase = BODY;
        return UDEKS_CBM_DIR_MORE;
    case BODY:
        if (byte != 0u) {
            if (directory->length == UDEKS_CBM_DIR_LINE_MAX)
                return fail(directory);
            directory->line[directory->length++] = byte;
            return UDEKS_CBM_DIR_MORE;
        }
        result = complete_line(directory, entry);
        if (result != UDEKS_CBM_DIR_ERROR) directory->phase = LINK_LOW;
        return result;
    case COMPLETE:
        return UDEKS_CBM_DIR_END;
    default:
        return UDEKS_CBM_DIR_ERROR;
    }
}

uint8_t udeks_cbm_dir_finish(struct udeks_cbm_directory *directory)
{
    if (!directory) return UDEKS_CBM_DIR_ERROR;
    if (directory->phase == COMPLETE) return UDEKS_CBM_DIR_END;
    /* Some drives end the stream after the footer NUL; the 1986 virtual
     * drive also emits one extra zero byte rather than a full zero link. */
    if (directory->saw_header && directory->saw_footer &&
        (directory->phase == LINK_LOW ||
         (directory->phase == LINK_HIGH && directory->link_low == 0u))) {
        directory->phase = COMPLETE;
        return UDEKS_CBM_DIR_END;
    }
    return fail(directory);
}

uint8_t udeks_cbm_dir_encode(const struct udeks_cbm_dir_entry *entry,
                             uint8_t *payload, uint8_t capacity)
{
    uint8_t i;
    if (!entry || !payload || entry->name_length == 0u ||
        entry->name_length > UDEKS_CBM_DIR_NAME_MAX ||
        capacity < entry->name_length + UDEKS_DIRENT_NAME)
        return 0u;
    payload[UDEKS_DIRENT_TYPE] = UDEKS_DT_REG;
    payload[UDEKS_DIRENT_NAME_LENGTH] = entry->name_length;
    for (i = 0u; i != entry->name_length; ++i)
        payload[UDEKS_DIRENT_NAME + i] = entry->name[i];
    return UDEKS_DIRENT_NAME + entry->name_length;
}
