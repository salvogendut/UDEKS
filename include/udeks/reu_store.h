/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_REU_STORE_H
#define UDEKS_REU_STORE_H
#include <stdint.h>

/* PRIVATE candidate graphics service, not installed and not a task ABI.
 * Serialized trusted callers authenticate the task before using its owner ID.
 * One object per owner, four disjoint 8 KiB extents in REU $000000-$007FFF.
 * This deliberately offers only 32 KiB, not all discovered expansion RAM.
 * Each extent fits the existing maximum bitmap (30 * 175 + 8 = 5258 bytes).
 * There is no shared-pool compaction, heap, or application-name special case.
 */
#define UDEKS_REU_STORE_SLOTS 4u
#define UDEKS_REU_STORE_LIMIT 8192u
#define UDEKS_REU_STORE_CHUNK 256u
#define UDEKS_REU_STORE_PENDING 1u
#define UDEKS_REU_STORE_READY 2u

/* Internal state is exposed for qualification/placement, NEVER to clients.
 * Starts in zeroed BSS. Handles monotonically increase; init does not reset
 * them. Exhaustion at 65535 fails closed until reboot, never wraps to an old
 * handle. release_owner must run before a task ID is recycled. */
struct udeks_reu_object {
    uint16_t owner, handle, size, received;
    uint8_t state;
};
struct udeks_reu_store_state {
    struct udeks_reu_object objects[UDEKS_REU_STORE_SLOTS];
    uint16_t serial;
    uint8_t device; /* 0 absent, 1 online, 2 transport fault */
};
extern struct udeks_reu_store_state udeks_reu_store;

/* Init accepts a successfully discovered capacity (0/2/4/8 64-KiB banks).
 * Requires no live objects; never probes or discards ownership itself.
 * Absent devices stay offline, letting the future adapter choose stock RAM. */
uint8_t udeks_reu_store_init(uint8_t banks);
uint8_t udeks_reu_store_begin(uint16_t owner, uint16_t size, uint16_t *handle);
uint8_t udeks_reu_store_write(uint16_t owner, uint16_t handle,
                            uint16_t offset, uint8_t *bytes, uint16_t count);
uint8_t udeks_reu_store_commit(uint16_t owner, uint16_t handle);
uint8_t udeks_reu_store_read(uint16_t owner, uint16_t handle,
                           uint16_t offset, uint8_t *bytes, uint16_t count);
uint8_t udeks_reu_store_release(uint16_t owner, uint16_t handle);
void udeks_reu_store_release_owner(uint16_t owner);

/* Binding supplied by the service (or qualification fixture). Must perform
 * exactly one synchronous bounded transfer, return 0 or errno, and not
 * yield/re-enter the store. Buffers are trusted, owned and non-overlapping
 * with store state; physical bank/MMU mapping belongs to this binding.
 * Every call is within an owned extent, <=256 bytes and below $8000.
 * On transport failure the whole store goes offline, no further read/write
 * or commit succeeds, and the failing read's output may be partially changed.
 * Release remains possible. Re-init requires releasing ALL objects plus a
 * fresh successful discovery. Never publish a partially uploaded object. */
uint8_t udeks_reu_store_io(uint8_t direction, uint16_t address,
                          uint8_t *bytes, uint16_t count);
#endif
