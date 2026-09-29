/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/kernel_bench.h"

typedef udeks_kernel_u16 (*syscall_fn)(udeks_kernel_u16 value);

struct kernel_event {
    udeks_kernel_u8 type;
    udeks_kernel_u8 source;
    udeks_kernel_u16 value;
};

#define QUEUE_CAPACITY 8u

static struct kernel_event event_queue[QUEUE_CAPACITY];
static udeks_kernel_u8 queue_head;
static udeks_kernel_u8 queue_tail;
static udeks_kernel_u8 queue_count;

static udeks_kernel_u16 sys_add(udeks_kernel_u16 value)
{
    return (udeks_kernel_u16)(value + 0x0101u);
}

static udeks_kernel_u16 sys_xor(udeks_kernel_u16 value)
{
    return (udeks_kernel_u16)(value ^ 0x5a5au);
}

static udeks_kernel_u16 sys_rotate(udeks_kernel_u16 value)
{
    return (udeks_kernel_u16)((value >> 1) | (value << 15));
}

static udeks_kernel_u16 sys_sub(udeks_kernel_u16 value)
{
    return (udeks_kernel_u16)(value - 0x001du);
}

static syscall_fn syscall_table[4];

void kernel_workload_prepare(void)
{
    /* Explicit setup avoids relying on target CRT initialized-data copying. */
    syscall_table[0] = sys_add;
    syscall_table[1] = sys_xor;
    syscall_table[2] = sys_rotate;
    syscall_table[3] = sys_sub;
}

static udeks_kernel_u8 queue_push(udeks_kernel_u8 type,
                                  udeks_kernel_u8 source,
                                  udeks_kernel_u16 value)
{
    struct kernel_event *event;

    if (queue_count == QUEUE_CAPACITY) {
        return 0u;
    }
    event = &event_queue[queue_tail];
    event->type = type;
    event->source = source;
    event->value = value;
    queue_tail = (udeks_kernel_u8)((queue_tail + 1u) & (QUEUE_CAPACITY - 1u));
    ++queue_count;
    return 1u;
}

static udeks_kernel_u8 queue_pop(struct kernel_event *event)
{
    if (queue_count == 0u) {
        return 0u;
    }
    *event = event_queue[queue_head];
    queue_head = (udeks_kernel_u8)((queue_head + 1u) & (QUEUE_CAPACITY - 1u));
    --queue_count;
    return 1u;
}

udeks_kernel_u16 kernel_workload_empty(void)
{
    return 0xbeefu;
}

udeks_kernel_u16 kernel_workload_switch_dispatch(void)
{
    udeks_kernel_u16 i;
    udeks_kernel_u16 state = 0x1357u;

    for (i = 0u; i < 128u; ++i) {
        switch ((udeks_kernel_u8)(state ^ i) & 3u) {
        case 0u:
            state = sys_add(state);
            break;
        case 1u:
            state = sys_xor(state);
            break;
        case 2u:
            state = sys_rotate(state);
            break;
        default:
            state = sys_sub(state);
            break;
        }
    }
    return state;
}

udeks_kernel_u16 kernel_workload_table_dispatch(void)
{
    udeks_kernel_u16 i;
    udeks_kernel_u16 state = 0x1357u;

    for (i = 0u; i < 128u; ++i) {
        udeks_kernel_u8 index = (udeks_kernel_u8)(state ^ i) & 3u;
        state = syscall_table[index](state);
    }
    return state;
}

udeks_kernel_u16 kernel_workload_event_queue(void)
{
    struct kernel_event event;
    udeks_kernel_u16 checksum = 0u;
    udeks_kernel_u8 round;
    udeks_kernel_u8 slot;
    udeks_kernel_u8 serial = 0u;

    queue_head = 0u;
    queue_tail = 0u;
    queue_count = 0u;
    for (round = 0u; round < 4u; ++round) {
        for (slot = 0u; slot < QUEUE_CAPACITY; ++slot) {
            if (!queue_push(serial, (udeks_kernel_u8)(serial ^ 0x5au),
                            (udeks_kernel_u16)(0x1200u + serial))) {
                return 0xffffu;
            }
            ++serial;
        }
        for (slot = 0u; slot < QUEUE_CAPACITY; ++slot) {
            if (!queue_pop(&event)) {
                return 0xffffu;
            }
            checksum = (udeks_kernel_u16)(checksum + event.type +
                       event.source + event.value);
        }
    }
    return checksum;
}
