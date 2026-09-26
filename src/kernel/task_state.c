/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/task_state.h"

#define TASK_SLOT_STRIDE    8u
#define TASK_SLOT_PARENT    0u
#define TASK_SLOT_STATE     1u
#define TASK_SLOT_WAIT      2u
#define TASK_SLOT_FLAGS     3u
#define TASK_SLOT_EXIT      4u
#define TASK_SLOT_DISPATCH  5u

#define TASK_STATE_INVALID  0xFFu

/*
 * Events ADMIT..CANCEL. Sources is a state bitmask; the next state depends
 * only on the event for every accepted pair.
 */
static const unsigned char task_event_sources[UDEKS_TASK_EVENT_CANCEL + 1u] = {
    0,
    0,
    (unsigned char)(1u << UDEKS_TASK_STATE_NEW),
    (unsigned char)(1u << UDEKS_TASK_STATE_RUNNABLE),
    (unsigned char)(1u << UDEKS_TASK_STATE_RUNNING),
    (unsigned char)(1u << UDEKS_TASK_STATE_RUNNING),
    (unsigned char)(1u << UDEKS_TASK_STATE_WAITING),
    (unsigned char)((1u << UDEKS_TASK_STATE_RUNNABLE) |
                    (1u << UDEKS_TASK_STATE_RUNNING) |
                    (1u << UDEKS_TASK_STATE_WAITING)),
    (unsigned char)(1u << UDEKS_TASK_STATE_STOPPED),
    (unsigned char)((1u << UDEKS_TASK_STATE_NEW) |
                    (1u << UDEKS_TASK_STATE_RUNNING)),
    (unsigned char)(1u << UDEKS_TASK_STATE_ZOMBIE),
    (unsigned char)((1u << UDEKS_TASK_STATE_NEW) |
                    (1u << UDEKS_TASK_STATE_RUNNABLE) |
                    (1u << UDEKS_TASK_STATE_RUNNING) |
                    (1u << UDEKS_TASK_STATE_WAITING) |
                    (1u << UDEKS_TASK_STATE_STOPPED))
};

static const unsigned char task_event_next[UDEKS_TASK_EVENT_CANCEL + 1u] = {
    0,
    UDEKS_TASK_STATE_NEW,
    UDEKS_TASK_STATE_RUNNABLE,
    UDEKS_TASK_STATE_RUNNING,
    UDEKS_TASK_STATE_RUNNABLE,
    UDEKS_TASK_STATE_WAITING,
    UDEKS_TASK_STATE_RUNNABLE,
    UDEKS_TASK_STATE_STOPPED,
    UDEKS_TASK_STATE_RUNNABLE,
    UDEKS_TASK_STATE_ZOMBIE,
    UDEKS_TASK_STATE_FREE,
    UDEKS_TASK_STATE_ZOMBIE
};

static const unsigned char task_state_bit[UDEKS_TASK_STATE_ZOMBIE + 1u] = {
    1u, 2u, 4u, 8u, 16u, 32u, 64u
};

static unsigned char task_slots[UDEKS_TASK_MAX_TASKS * TASK_SLOT_STRIDE];
static unsigned char current_task;
static unsigned char rejected_transitions;
static unsigned char canary_failures;
static unsigned char last_event;
static unsigned char table_ready;
static unsigned int switch_count;

static unsigned char *task_slot(unsigned char id)
{
    if (id < 1u || id > UDEKS_TASK_MAX_TASKS) {
        return 0;
    }
    return &task_slots[(unsigned char)((id - 1u) * TASK_SLOT_STRIDE)];
}

unsigned char udeks_task_state_reset(void)
{
    unsigned char index;

    for (index = 0; index < (unsigned char)sizeof(task_slots); ++index) {
        task_slots[index] = 0;
    }
    current_task = UDEKS_TASK_ID_NONE;
    rejected_transitions = 0;
    canary_failures = 0;
    last_event = 0;
    table_ready = 1;
    switch_count = 0;
    return UDEKS_TASK_OK;
}

unsigned char udeks_task_state_create(
    unsigned char id, unsigned char parent, unsigned char flags)
{
    unsigned char *slot;

    slot = task_slot(id);
    if (slot == 0) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_ID;
    }
    if (slot[TASK_SLOT_STATE] != UDEKS_TASK_STATE_FREE) {
        ++rejected_transitions;
        return UDEKS_TASK_EXISTS;
    }
    if (parent != UDEKS_TASK_ID_NONE && task_slot(parent) == 0) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_ID;
    }
    slot[TASK_SLOT_PARENT] = parent;
    slot[TASK_SLOT_FLAGS] = flags;
    slot[TASK_SLOT_STATE] = UDEKS_TASK_STATE_NEW;
    last_event = UDEKS_TASK_EVENT_CREATE;
    return UDEKS_TASK_OK;
}

unsigned char udeks_task_state_apply(
    unsigned char id, unsigned char event, unsigned char argument)
{
    unsigned char *slot;

    slot = task_slot(id);
    if (slot == 0) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_ID;
    }
    if (event <= UDEKS_TASK_EVENT_CREATE ||
        event > UDEKS_TASK_EVENT_CANCEL) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_EVENT;
    }

    if (event == UDEKS_TASK_EVENT_DISPATCH) {
        if (current_task != UDEKS_TASK_ID_NONE && current_task != id) {
            ++rejected_transitions;
            return UDEKS_TASK_BUSY;
        }
        if (current_task == id &&
            slot[TASK_SLOT_STATE] == UDEKS_TASK_STATE_RUNNING) {
            last_event = event;
            return UDEKS_TASK_OK;
        }
    }
    if ((task_event_sources[event] &
         task_state_bit[slot[TASK_SLOT_STATE]]) == 0) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_STATE;
    }
    if (event == UDEKS_TASK_EVENT_BLOCK &&
        (argument == UDEKS_TASK_WAIT_NONE ||
         argument > UDEKS_TASK_WAIT_TERMINAL)) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_REASON;
    }

    if (event == UDEKS_TASK_EVENT_DISPATCH) {
        current_task = id;
        ++switch_count;
        ++slot[TASK_SLOT_DISPATCH];
    } else if (current_task == id) {
        current_task = UDEKS_TASK_ID_NONE;
    }
    if (event == UDEKS_TASK_EVENT_BLOCK) {
        slot[TASK_SLOT_WAIT] = argument;
    } else {
        slot[TASK_SLOT_WAIT] = UDEKS_TASK_WAIT_NONE;
        if (event == UDEKS_TASK_EVENT_EXIT) {
            slot[TASK_SLOT_EXIT] = argument;
        } else if (event == UDEKS_TASK_EVENT_CANCEL) {
            slot[TASK_SLOT_EXIT] = 0;
        }
    }

    slot[TASK_SLOT_STATE] = task_event_next[event];
    last_event = event;
    return UDEKS_TASK_OK;
}

unsigned char udeks_task_state_get(unsigned char id)
{
    unsigned char *slot;

    slot = task_slot(id);
    if (slot == 0) {
        return TASK_STATE_INVALID;
    }
    return slot[TASK_SLOT_STATE];
}

unsigned char udeks_task_state_current(void)
{
    return current_task;
}

unsigned char udeks_task_state_runnable_count(void)
{
    unsigned char count;
    unsigned char index;

    count = 0;
    for (index = 0; index < UDEKS_TASK_MAX_TASKS; ++index) {
        if (task_slots[index * TASK_SLOT_STRIDE + TASK_SLOT_STATE] ==
                UDEKS_TASK_STATE_RUNNABLE ||
            task_slots[index * TASK_SLOT_STRIDE + TASK_SLOT_STATE] ==
                UDEKS_TASK_STATE_RUNNING) {
            ++count;
        }
    }
    return count;
}

unsigned char udeks_task_state_defined_count(void)
{
    unsigned char count;
    unsigned char index;

    count = 0;
    for (index = 0; index < UDEKS_TASK_MAX_TASKS; ++index) {
        if (task_slots[index * TASK_SLOT_STRIDE + TASK_SLOT_STATE] !=
                UDEKS_TASK_STATE_FREE) {
            ++count;
        }
    }
    return count;
}

unsigned int udeks_task_state_switch_count(void)
{
    return switch_count;
}

unsigned char udeks_task_state_rejected_count(void)
{
    return rejected_transitions;
}

unsigned char udeks_task_state_canary_failures(void)
{
    return canary_failures;
}

void udeks_task_state_note_canary_failure(void)
{
    ++canary_failures;
}

void udeks_task_state_publish(unsigned char *record)
{
    unsigned int switches;

    record[UDEKS_UTSK_MAGIC0] = 'U';
    record[UDEKS_UTSK_MAGIC1] = 'T';
    record[UDEKS_UTSK_MAGIC2] = 'S';
    record[UDEKS_UTSK_MAGIC3] = 'K';
    record[UDEKS_UTSK_ABI_MAJOR] = UDEKS_TASK_STATE_ABI_MAJOR;
    record[UDEKS_UTSK_ABI_MINOR] = UDEKS_TASK_STATE_ABI_MINOR;
    if (table_ready != 0) {
        record[UDEKS_UTSK_STATE] = UDEKS_TASK_STATE_READY;
    } else {
        record[UDEKS_UTSK_STATE] = (unsigned char)(
            UDEKS_TASK_STATE_ERROR | 1u);
    }
    record[UDEKS_UTSK_CURRENT] = current_task;
    record[UDEKS_UTSK_RUNNABLE] = udeks_task_state_runnable_count();
    record[UDEKS_UTSK_DEFINED] = udeks_task_state_defined_count();
    record[UDEKS_UTSK_REJECTED] = rejected_transitions;
    record[UDEKS_UTSK_CANARY] = canary_failures;
    switches = switch_count;
    record[UDEKS_UTSK_SWITCHES_LO] = (unsigned char)(switches & 0xFFu);
    record[UDEKS_UTSK_SWITCHES_HI] = (unsigned char)(switches >> 8);
    record[UDEKS_UTSK_LAST_EVENT] = last_event;
    record[UDEKS_UTSK_RESERVED] = 0;
}
