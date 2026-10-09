/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/reu.h"
#include "udeks/reu_store.h"

/* Named absolute binding avoids cc65's optimizer reusing ptr1 across the
 * verification loop for a constant-pointer compound assignment. */
extern volatile uint8_t store_result[32];
#define R store_result
#define CONFIG (*(volatile uint8_t *)0x70f0u)
#define CORRUPT (*(volatile uint8_t *)0x70f1u)
#define RCR (*(volatile uint8_t *)0xd506u)
#define CR (*(volatile uint8_t *)0xff00u)
#define SPEED (*(volatile uint8_t *)0xd030u)
#define PEER ((volatile uint8_t *)0x6000u)

void __fastcall__ store_to_bank1(uint8_t *bytes);
void __fastcall__ store_from_bank1(uint8_t *bytes);
uint8_t store_bank1_guards(void);
static uint8_t buffer[256], inject;
static uint16_t handles[4];
static const uint8_t owners[4] = {2, 3, 5, 6};
static const uint16_t chunks[4] = {19, 255, 256, 31};

static void fail(uint8_t code)
{
    R[6] = code;
    R[5] = 128;
    for (;;) {}
}

static void increment(uint8_t offset)
{
    if (!++R[offset]) ++R[offset+1];
}

static void reject(uint8_t actual, uint8_t expected)
{
    if (actual != expected) fail(2);
    ++R[14];
}

static uint8_t pattern(uint8_t owner, uint16_t at)
{
    return (uint8_t)(owner * 31u + (at ^ (at >> 8)));
}

uint8_t udeks_reu_store_io(uint8_t direction, uint16_t address,
                          uint8_t *bytes, uint16_t count)
{
    uint8_t error;
    unsigned int host_count;
    if (RCR != 0x49 || CR != 0x3e || (SPEED & 1u)) fail(3);
    host_count = inject ? (count + 1u)/2u : count;
    udeks_reu_request[0] = direction;
    udeks_reu_request[1] = 1;
    udeks_reu_request[2] = 0;
    udeks_reu_request[3] = 0x60;
    udeks_reu_request[4] = (uint8_t)address;
    udeks_reu_request[5] = (uint8_t)(address >> 8);
    udeks_reu_request[6] = 0;
    udeks_reu_request[7] = (uint8_t)host_count;
    udeks_reu_request[8] = (uint8_t)(host_count >> 8);
    if (!direction) store_to_bank1(bytes);
    error = udeks_reu_transfer();
    increment(10);
    if (!error && direction) {
        /* REC advanced its registers, not the software request. */
        store_from_bank1(bytes);
        if (CORRUPT) bytes[0] ^= 1; /* independent negative readback control */
    }
    if (RCR != 0x49 || CR != 0x3e || (SPEED & 1u)) fail(3);
    if (store_bank1_guards()) fail(4);
    return inject ? 5 : error;
}

void store_probe(void)
{
    uint8_t i, error;
    uint16_t at, count, j, fresh = 0xbeef;
    memset((void *)R, 0, 32);
    memcpy((void *)R, "RSTQ", 4);
    R[4] = R[5] = 1;
    R[7] = CONFIG;
    R[19] = sizeof(udeks_reu_store);
    error = udeks_reu_discover();
    R[8] = udeks_reu_capacity_banks;
    if (R[8] != (CONFIG > 8 ? 8 : CONFIG) || error != (CONFIG ? 0 : 19)) fail(1);
    if (udeks_reu_store_init(R[8])) fail(1);
    if (!CONFIG) {
        reject(udeks_reu_store_begin(2, 2008, &fresh), 19);
        if (fresh != 0xbeef) fail(1);
        R[9] = 1;
        R[5] = 2;
        return;
    }
    /* A display-safe DMA choice: stage in the SAME physical bank selected
     * for VIC. This fixture does NOT qualify live desktop/IRQ/NMI behavior. */
    RCR = 0x49;
    for (j = 0; j != 256; ++j) PEER[j] = (uint8_t)(j ^ 0xa5u);
    for (i = 0; i != 4; ++i)
        if (udeks_reu_store_begin(owners[i], 8192, handles+i)) fail(5);
    reject(udeks_reu_store_begin(4, 1, &fresh), 12);
    if (fresh != 0xbeef) fail(5);
    reject(udeks_reu_store_begin(2, 1, &fresh), 16);
    reject(udeks_reu_store_read(2, handles[0], 0, buffer, 1), 22);
    reject(udeks_reu_store_commit(2, handles[0]), 22);
    reject(udeks_reu_store_write(3, handles[0], 0, buffer, 1), 9);
    reject(udeks_reu_store_write(2, handles[0], 1, buffer, 1), 22);
    reject(udeks_reu_store_write(2, handles[0], 0, buffer, 0), 22);
    reject(udeks_reu_store_write(2, handles[0], 0, buffer, 257), 22);
    for (i = 0; i != 4; ++i) {
        at = 0;
        while (at != 8192) {
            count = chunks[i];
            if (count > 8192-at) count = 8192-at;
            for (j = 0; j != count; ++j) buffer[j] = pattern(owners[i], at+j);
            if (udeks_reu_store_write(owners[i], handles[i], at, buffer, count)) fail(6);
            at += count;
        }
        if (udeks_reu_store_commit(owners[i], handles[i])) fail(7);
    }
    R[9] = 1;
    /* Read all four AFTER all writes. A cross-wired bank, slot, stale extent
     * or aliased allocation cannot pass by echoing the last written buffer. */
    for (i = 0; i != 4; ++i) {
        at = 0;
        while (at != 8192) {
            count = 30;
            if (count > 8192-at) count = 8192-at;
            memset(buffer, 0xcd, 256);
            if (udeks_reu_store_read(owners[i], handles[i], at, buffer, count)) fail(8);
            for (j = 0; j != count; ++j) {
                if (buffer[j] != pattern(owners[i], at+j)) fail(9);
                increment(12);
            }
            for (; j != 256; ++j) if (buffer[j] != 0xcd) fail(10);
            at += count;
        }
    }
    R[9] |= 2;
    reject(udeks_reu_store_read(2, handles[0], 8191, buffer, 2), 22);
    reject(udeks_reu_store_write(2, handles[0], 8192, buffer, 1), 22);
    for (i = 0; i != 4; ++i) udeks_reu_store_release_owner(owners[i]);
    if (udeks_reu_store_init(R[8]) || udeks_reu_store_begin(2, 19, &fresh)) fail(11);
    if (fresh == handles[0]) fail(11);
    reject(udeks_reu_store_release(2, handles[0]), 9);
    inject = 1;
    memset(buffer, 0xee, 19);
    reject(udeks_reu_store_write(2, fresh, 0, buffer, 19), 5);
    ++R[15];
    inject = 0;
    if (udeks_reu_store.objects[0].received || udeks_reu_store.device != 2) fail(12);
    reject(udeks_reu_store_write(2, fresh, 0, buffer, 19), 5);
    reject(udeks_reu_store_init(R[8]), 16);
    udeks_reu_store_release_owner(2);
    if (udeks_reu_discover() || udeks_reu_capacity_banks != R[8]) fail(13);
    if (udeks_reu_store_init(R[8]) || udeks_reu_store_begin(2, 1, &fresh)) fail(13);
    buffer[0] = 0x73;
    if (udeks_reu_store_write(2, fresh, 0, buffer, 1) ||
        udeks_reu_store_commit(2, fresh)) fail(13);
    buffer[0] = 0;
    if (udeks_reu_store_read(2, fresh, 0, buffer, 1) || buffer[0] != 0x73) fail(13);
    increment(12);
    udeks_reu_store_release_owner(2);
    R[9] |= 4;
    for (j = 0; j != 256; ++j)
        if (PEER[j] != (uint8_t)(j ^ 0xa5u)) fail(14);
    if (store_bank1_guards()) fail(4);
    R[16] = 2;
    R[17] = (uint8_t)udeks_reu_store.serial;
    R[18] = (uint8_t)(udeks_reu_store.serial >> 8);
    R[5] = 2;
}
