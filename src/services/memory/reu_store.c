/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/reu_store.h"

struct udeks_reu_store_state udeks_reu_store;

static uint8_t available(void)
{
    return udeks_reu_store.device == 1 ? 0 :
           (udeks_reu_store.device == 2 ? 5 : 19);
}

static struct udeks_reu_object *find(uint16_t owner, uint16_t handle)
{
    uint8_t i;
    if (owner && handle)
        for (i = 0; i != UDEKS_REU_STORE_SLOTS; ++i)
            if (udeks_reu_store.objects[i].owner == owner &&
                udeks_reu_store.objects[i].handle == handle)
                return udeks_reu_store.objects + i;
    return 0;
}

uint8_t udeks_reu_store_init(uint8_t banks)
{
    uint8_t i;
    if (banks && banks != 2 && banks != 4 && banks != 8) return 22;
    for (i = 0; i != UDEKS_REU_STORE_SLOTS; ++i)
        if (udeks_reu_store.objects[i].owner) return 16;
    udeks_reu_store.device = banks ? 1 : 0;
    return 0;
}

uint8_t udeks_reu_store_begin(uint16_t owner, uint16_t size, uint16_t *handle)
{
    uint8_t i, free_slot = UDEKS_REU_STORE_SLOTS, error;
    struct udeks_reu_object *object;
    if (!owner || !handle || !size || size > UDEKS_REU_STORE_LIMIT) return 22;
    error = available();
    if (error) return error;
    for (i = 0; i != UDEKS_REU_STORE_SLOTS; ++i) {
        if (udeks_reu_store.objects[i].owner == owner) return 16;
        if (!udeks_reu_store.objects[i].owner && free_slot == UDEKS_REU_STORE_SLOTS)
            free_slot = i;
    }
    if (free_slot == UDEKS_REU_STORE_SLOTS || udeks_reu_store.serial == 65535u)
        return 12;
    object = udeks_reu_store.objects + free_slot;
    object->owner = owner;
    object->handle = ++udeks_reu_store.serial;
    object->size = size;
    object->received = 0;
    object->state = UDEKS_REU_STORE_PENDING;
    *handle = object->handle;
    return 0;
}

static uint8_t transfer(uint8_t direction, struct udeks_reu_object *object,
                        uint16_t offset, uint8_t *bytes, uint16_t count)
{
    uint8_t error;
    uint16_t address;
    if (!bytes || !count || count > UDEKS_REU_STORE_CHUNK ||
        offset > object->size || count > object->size - offset) return 22;
    error = available();
    if (error) return error;
    address = (uint16_t)(object - udeks_reu_store.objects) * UDEKS_REU_STORE_LIMIT;
    error = udeks_reu_store_io(direction, address + offset, bytes, count);
    if (error) {
        /* DMA may have partially executed: never retry/commit this object or
         * continue trusting other expansion contents after a device fault. */
        udeks_reu_store.device = 2;
        return 5;
    }
    return 0;
}

uint8_t udeks_reu_store_write(uint16_t owner, uint16_t handle,
                            uint16_t offset, uint8_t *bytes, uint16_t count)
{
    struct udeks_reu_object *object;
    uint8_t error;
    object = find(owner, handle);
    if (!object) return 9;
    if (object->state != UDEKS_REU_STORE_PENDING || offset != object->received)
        return 22;
    error = transfer(0, object, offset, bytes, count);
    if (!error) object->received += count;
    return error;
}

uint8_t udeks_reu_store_commit(uint16_t owner, uint16_t handle)
{
    struct udeks_reu_object *object;
    uint8_t error;
    object = find(owner, handle);
    if (!object) return 9;
    if (object->state != UDEKS_REU_STORE_PENDING || object->received != object->size)
        return 22;
    error = available();
    if (error) return error;
    object->state = UDEKS_REU_STORE_READY;
    return 0;
}

uint8_t udeks_reu_store_read(uint16_t owner, uint16_t handle,
                           uint16_t offset, uint8_t *bytes, uint16_t count)
{
    struct udeks_reu_object *object;
    object = find(owner, handle);
    if (!object) return 9;
    if (object->state != UDEKS_REU_STORE_READY) return 22;
    return transfer(1, object, offset, bytes, count);
}

uint8_t udeks_reu_store_release(uint16_t owner, uint16_t handle)
{
    struct udeks_reu_object *object;
    object = find(owner, handle);
    if (!object) return 9;
    memset(object, 0, sizeof(*object));
    return 0;
}

void udeks_reu_store_release_owner(uint16_t owner)
{
    uint8_t i;
    if (!owner) return;
    for (i = 0; i != UDEKS_REU_STORE_SLOTS; ++i)
        if (udeks_reu_store.objects[i].owner == owner)
            memset(udeks_reu_store.objects + i, 0, sizeof(struct udeks_reu_object));
}
