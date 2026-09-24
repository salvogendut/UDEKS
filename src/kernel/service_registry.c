/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/service.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_SERVICE_STATUS_BASE + (offset)))

#define REGISTRY_ERROR_EMPTY          1u
#define REGISTRY_ERROR_MAGIC          2u
#define REGISTRY_ERROR_VERSION        3u
#define REGISTRY_ERROR_SIZE           4u
#define REGISTRY_ERROR_CLASS          5u
#define REGISTRY_ERROR_START_VECTOR   6u
#define REGISTRY_ERROR_START_FAILED   7u

typedef unsigned char (*service_entry)(void);

union service_pointer {
    const unsigned char *data;
    service_entry entry;
    unsigned char byte[2];
};

extern const unsigned char udeks_service_table[];
extern const unsigned char udeks_service_count;

static union service_pointer service_pointer;
static const unsigned char *descriptor;
static unsigned char service_index;
static unsigned char table_offset;
static unsigned char start_result;

static void registry_status_begin(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_SERVICE_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'S';
    STATUS_BYTE(1) = 'R';
    STATUS_BYTE(2) = 'E';
    STATUS_BYTE(3) = 'G';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_SERVICE_STATE_STARTING;
    STATUS_BYTE(13) = UDEKS_SERVICE_ABI_MAJOR;
    STATUS_BYTE(14) = UDEKS_SERVICE_ABI_MINOR;
    STATUS_BYTE(17) = udeks_service_count;
}

static unsigned char registry_fail(unsigned char code)
{
    STATUS_BYTE(6) = code;
    ++STATUS_BYTE(9);
    STATUS_BYTE(5) = (unsigned char)(UDEKS_SERVICE_STATE_ERROR | code);
    return code;
}

static unsigned char descriptor_is_valid(void)
{
    if (descriptor[UDEKS_SERVICE_MAGIC0] != 'U' ||
        descriptor[UDEKS_SERVICE_MAGIC1] != 'S' ||
        descriptor[UDEKS_SERVICE_MAGIC2] != 'V' ||
        descriptor[UDEKS_SERVICE_MAGIC3] != 'C') {
        return REGISTRY_ERROR_MAGIC;
    }
    if (descriptor[UDEKS_SERVICE_ABI_MAJOR_OFFSET] !=
            UDEKS_SERVICE_ABI_MAJOR ||
        descriptor[UDEKS_SERVICE_ABI_MINOR_OFFSET] > UDEKS_SERVICE_ABI_MINOR) {
        return REGISTRY_ERROR_VERSION;
    }
    if (descriptor[UDEKS_SERVICE_SIZE_OFFSET] !=
            UDEKS_SERVICE_DESCRIPTOR_SIZE) {
        return REGISTRY_ERROR_SIZE;
    }
    if (descriptor[UDEKS_SERVICE_CLASS_OFFSET] == 0) {
        return REGISTRY_ERROR_CLASS;
    }
    if (descriptor[UDEKS_SERVICE_START_LO] == 0 &&
        descriptor[UDEKS_SERVICE_START_HI] == 0) {
        return REGISTRY_ERROR_START_VECTOR;
    }
    return 0;
}

unsigned char udeks_service_start_all(void)
{
    unsigned char validation;

    registry_status_begin();
    if (udeks_service_count == 0) {
        return registry_fail(REGISTRY_ERROR_EMPTY);
    }

    table_offset = 0;
    for (service_index = 0; service_index < udeks_service_count; ++service_index) {
        service_pointer.byte[0] = udeks_service_table[table_offset];
        ++table_offset;
        service_pointer.byte[1] = udeks_service_table[table_offset];
        ++table_offset;
        descriptor = service_pointer.data;
        ++STATUS_BYTE(7);

        STATUS_BYTE(10) = descriptor[UDEKS_SERVICE_CLASS_OFFSET];
        STATUS_BYTE(11) = descriptor[UDEKS_SERVICE_INSTANCE_OFFSET];
        STATUS_BYTE(15) = descriptor[UDEKS_SERVICE_SIZE_OFFSET];
        STATUS_BYTE(16) = descriptor[UDEKS_SERVICE_FLAGS_OFFSET];

        validation = descriptor_is_valid();
        if (validation != 0) {
            return registry_fail(validation);
        }

        service_pointer.byte[0] = descriptor[UDEKS_SERVICE_START_LO];
        service_pointer.byte[1] = descriptor[UDEKS_SERVICE_START_HI];
        start_result = service_pointer.entry();
        STATUS_BYTE(12) = start_result;
        if (start_result != 0) {
            return registry_fail(REGISTRY_ERROR_START_FAILED);
        }
        ++STATUS_BYTE(8);
    }

    STATUS_BYTE(5) = UDEKS_SERVICE_STATE_READY;
    return 0;
}
