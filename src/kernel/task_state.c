/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/task_state.h"

#define TASK_SLOT_STRIDE    8u
#define TASK_SLOT_PARENT    0u
#define TASK_SLOT_STATE     1u
#define TASK_SLOT_WAIT      2u
#define TASK_SLOT_FLAGS     3u
#define TASK_SLOT_EXIT      4u
#define TASK_SLOT_DISPATCH  5u
#define TASK_SLOT_RESUME    6u

#define TASK_FLAG_MASK \
    (UDEKS_LIFECYCLE_FLAG_USER | UDEKS_LIFECYCLE_FLAG_PERSISTENT)

/*
 * Events ADMIT..CANCEL. Sources is a state bitmask; the next state depends
 * only on the event for every accepted pair.
 */
static const unsigned char task_event_sources[UDEKS_LIFECYCLE_EVENT_CANCEL + 1u] = {
    0,
    0,
    (unsigned char)(1u << UDEKS_LIFECYCLE_STATE_NEW),
    (unsigned char)(1u << UDEKS_LIFECYCLE_STATE_RUNNABLE),
    (unsigned char)(1u << UDEKS_LIFECYCLE_STATE_RUNNING),
    (unsigned char)(1u << UDEKS_LIFECYCLE_STATE_RUNNING),
    (unsigned char)((1u << UDEKS_LIFECYCLE_STATE_WAITING) |
                    (1u << UDEKS_LIFECYCLE_STATE_STOPPED)),
    (unsigned char)((1u << UDEKS_LIFECYCLE_STATE_RUNNABLE) |
                    (1u << UDEKS_LIFECYCLE_STATE_RUNNING) |
                    (1u << UDEKS_LIFECYCLE_STATE_WAITING)),
    (unsigned char)(1u << UDEKS_LIFECYCLE_STATE_STOPPED),
    (unsigned char)((1u << UDEKS_LIFECYCLE_STATE_NEW) |
                    (1u << UDEKS_LIFECYCLE_STATE_RUNNING)),
    (unsigned char)(1u << UDEKS_LIFECYCLE_STATE_ZOMBIE),
    (unsigned char)((1u << UDEKS_LIFECYCLE_STATE_NEW) |
                    (1u << UDEKS_LIFECYCLE_STATE_RUNNABLE) |
                    (1u << UDEKS_LIFECYCLE_STATE_RUNNING) |
                    (1u << UDEKS_LIFECYCLE_STATE_WAITING) |
                    (1u << UDEKS_LIFECYCLE_STATE_STOPPED))
};

static const unsigned char task_event_next[UDEKS_LIFECYCLE_EVENT_CANCEL + 1u] = {
    0,
    UDEKS_LIFECYCLE_STATE_NEW,
    UDEKS_LIFECYCLE_STATE_RUNNABLE,
    UDEKS_LIFECYCLE_STATE_RUNNING,
    UDEKS_LIFECYCLE_STATE_RUNNABLE,
    UDEKS_LIFECYCLE_STATE_WAITING,
    UDEKS_LIFECYCLE_STATE_RUNNABLE,
    UDEKS_LIFECYCLE_STATE_STOPPED,
    UDEKS_LIFECYCLE_STATE_RUNNABLE,
    UDEKS_LIFECYCLE_STATE_ZOMBIE,
    UDEKS_LIFECYCLE_STATE_FREE,
    UDEKS_LIFECYCLE_STATE_ZOMBIE
};

static const unsigned char task_state_bit[UDEKS_LIFECYCLE_STATE_ZOMBIE + 1u] = {
    1u, 2u, 4u, 8u, 16u, 32u, 64u
};

/* Private link-time anchors used by the bounded lifecycle handler. They are
 * not public ABI; the generated bridge binds them from the overlay map. */
unsigned char udeks_lifecycle_slots_private[
    UDEKS_LIFECYCLE_MAX_TASKS * TASK_SLOT_STRIDE];
unsigned char udeks_lifecycle_current_private;
unsigned char udeks_lifecycle_rejected_private;
static unsigned char canary_failures;
unsigned char udeks_lifecycle_last_event_private;
static unsigned char table_ready;
static unsigned int switch_count;

static unsigned char *task_slot(unsigned char id)
{
    if (id < 1u || id > UDEKS_LIFECYCLE_MAX_TASKS) {
        return 0;
    }
    return &udeks_lifecycle_slots_private[
        (unsigned char)((id - 1u) * TASK_SLOT_STRIDE)];
}

static void task_slot_clear(unsigned char *slot)
{
    unsigned char index;

    for (index = 0; index < TASK_SLOT_STRIDE; ++index) {
        slot[index] = 0;
    }
}

unsigned char udeks_lifecycle_reset(void)
{
    unsigned char index;

    for (index = 0;
         index < (unsigned char)sizeof(udeks_lifecycle_slots_private);
         ++index) {
        udeks_lifecycle_slots_private[index] = 0;
    }
    udeks_lifecycle_current_private = UDEKS_LIFECYCLE_ID_NONE;
    udeks_lifecycle_rejected_private = 0;
    canary_failures = 0;
    udeks_lifecycle_last_event_private = 0;
    table_ready = 1;
    switch_count = 0;
    return UDEKS_LIFECYCLE_OK;
}

unsigned char udeks_lifecycle_create(
    unsigned char id, unsigned char parent, unsigned char flags)
{
    unsigned char *slot;
    unsigned char *parent_slot;

    slot = task_slot(id);
    if (slot == 0) {
        ++udeks_lifecycle_rejected_private;
        return UDEKS_LIFECYCLE_BAD_ID;
    }
    if ((flags & (unsigned char)~TASK_FLAG_MASK) != 0) {
        ++udeks_lifecycle_rejected_private;
        return UDEKS_LIFECYCLE_BAD_FLAGS;
    }
    if (slot[TASK_SLOT_STATE] != UDEKS_LIFECYCLE_STATE_FREE) {
        ++udeks_lifecycle_rejected_private;
        return UDEKS_LIFECYCLE_EXISTS;
    }
    if (parent != UDEKS_LIFECYCLE_ID_NONE) {
        parent_slot = task_slot(parent);
        if (parent == id || parent_slot == 0 ||
            parent_slot[TASK_SLOT_STATE] == UDEKS_LIFECYCLE_STATE_FREE ||
            parent_slot[TASK_SLOT_STATE] == UDEKS_LIFECYCLE_STATE_ZOMBIE) {
            ++udeks_lifecycle_rejected_private;
            return UDEKS_LIFECYCLE_BAD_ID;
        }
    }

    task_slot_clear(slot);
    slot[TASK_SLOT_PARENT] = parent;
    slot[TASK_SLOT_FLAGS] = flags;
    slot[TASK_SLOT_STATE] = UDEKS_LIFECYCLE_STATE_NEW;
    udeks_lifecycle_last_event_private = UDEKS_LIFECYCLE_EVENT_CREATE;
    return UDEKS_LIFECYCLE_OK;
}

#ifdef __CC65__
#pragma code-name(push, "SCHEDULER")
#endif
unsigned char udeks_lifecycle_apply(
    unsigned char id, unsigned char event, unsigned char argument)
{
    unsigned char *slot;
    unsigned char state;
    unsigned char next;

    slot = task_slot(id);
    if (slot == 0) {
        ++udeks_lifecycle_rejected_private;
        return UDEKS_LIFECYCLE_BAD_ID;
    }
    if (event <= UDEKS_LIFECYCLE_EVENT_CREATE ||
        event > UDEKS_LIFECYCLE_EVENT_CANCEL) {
        ++udeks_lifecycle_rejected_private;
        return UDEKS_LIFECYCLE_BAD_EVENT;
    }
    state = slot[TASK_SLOT_STATE];

    if (event == UDEKS_LIFECYCLE_EVENT_DISPATCH) {
        if (udeks_lifecycle_current_private != UDEKS_LIFECYCLE_ID_NONE &&
            udeks_lifecycle_current_private != id) {
            ++udeks_lifecycle_rejected_private;
            return UDEKS_LIFECYCLE_BUSY;
        }
        if (udeks_lifecycle_current_private == id &&
            state == UDEKS_LIFECYCLE_STATE_RUNNING) {
            udeks_lifecycle_last_event_private = event;
            return UDEKS_LIFECYCLE_OK;
        }
    }
    if ((task_event_sources[event] & task_state_bit[state]) == 0) {
        ++udeks_lifecycle_rejected_private;
        return UDEKS_LIFECYCLE_BAD_STATE;
    }
    if (event == UDEKS_LIFECYCLE_EVENT_UNBLOCK &&
        state == UDEKS_LIFECYCLE_STATE_STOPPED &&
        (slot[TASK_SLOT_RESUME] != UDEKS_LIFECYCLE_STATE_WAITING ||
         slot[TASK_SLOT_WAIT] == UDEKS_LIFECYCLE_WAIT_NONE)) {
        ++udeks_lifecycle_rejected_private;
        return UDEKS_LIFECYCLE_BAD_STATE;
    }
    if (event == UDEKS_LIFECYCLE_EVENT_BLOCK &&
        (argument == UDEKS_LIFECYCLE_WAIT_NONE ||
         argument > UDEKS_LIFECYCLE_WAIT_TERMINAL)) {
        ++udeks_lifecycle_rejected_private;
        return UDEKS_LIFECYCLE_BAD_REASON;
    }

    next = task_event_next[event];

    if (event == UDEKS_LIFECYCLE_EVENT_DISPATCH) {
        udeks_lifecycle_current_private = id;
        ++switch_count;
        ++slot[TASK_SLOT_DISPATCH];
    } else if (udeks_lifecycle_current_private == id) {
        udeks_lifecycle_current_private = UDEKS_LIFECYCLE_ID_NONE;
    }

    if (event == UDEKS_LIFECYCLE_EVENT_BLOCK) {
        slot[TASK_SLOT_WAIT] = argument;
    } else if (event == UDEKS_LIFECYCLE_EVENT_UNBLOCK) {
        slot[TASK_SLOT_WAIT] = UDEKS_LIFECYCLE_WAIT_NONE;
        if (state == UDEKS_LIFECYCLE_STATE_STOPPED) {
            next = UDEKS_LIFECYCLE_STATE_STOPPED;
            slot[TASK_SLOT_RESUME] = UDEKS_LIFECYCLE_STATE_RUNNABLE;
        } else {
            slot[TASK_SLOT_RESUME] = UDEKS_LIFECYCLE_STATE_FREE;
        }
    } else if (event == UDEKS_LIFECYCLE_EVENT_STOP) {
        if (state == UDEKS_LIFECYCLE_STATE_WAITING) {
            slot[TASK_SLOT_RESUME] = UDEKS_LIFECYCLE_STATE_WAITING;
        } else {
            slot[TASK_SLOT_RESUME] = UDEKS_LIFECYCLE_STATE_RUNNABLE;
        }
    } else if (event == UDEKS_LIFECYCLE_EVENT_CONTINUE) {
        if (slot[TASK_SLOT_RESUME] == UDEKS_LIFECYCLE_STATE_WAITING) {
            next = UDEKS_LIFECYCLE_STATE_WAITING;
        } else {
            next = UDEKS_LIFECYCLE_STATE_RUNNABLE;
        }
        slot[TASK_SLOT_RESUME] = UDEKS_LIFECYCLE_STATE_FREE;
    } else {
        slot[TASK_SLOT_WAIT] = UDEKS_LIFECYCLE_WAIT_NONE;
        slot[TASK_SLOT_RESUME] = UDEKS_LIFECYCLE_STATE_FREE;
        if (event == UDEKS_LIFECYCLE_EVENT_EXIT ||
            event == UDEKS_LIFECYCLE_EVENT_CANCEL) {
            slot[TASK_SLOT_EXIT] = argument;
        }
    }

    if (event == UDEKS_LIFECYCLE_EVENT_REAP) {
        task_slot_clear(slot);
    }
    slot[TASK_SLOT_STATE] = next;
    udeks_lifecycle_last_event_private = event;
    return UDEKS_LIFECYCLE_OK;
}
#ifdef __CC65__
#pragma code-name(pop)
#endif

unsigned char udeks_lifecycle_get(unsigned char id)
{
    unsigned char *slot;

    slot = task_slot(id);
    if (slot == 0) {
        return UDEKS_LIFECYCLE_INVALID;
    }
    return slot[TASK_SLOT_STATE];
}

unsigned char udeks_lifecycle_parent(unsigned char id)
{
    unsigned char *slot;

    slot = task_slot(id);
    if (slot == 0) {
        return UDEKS_LIFECYCLE_INVALID;
    }
    return slot[TASK_SLOT_PARENT];
}

unsigned char udeks_lifecycle_wait_reason(unsigned char id)
{
    unsigned char *slot;

    slot = task_slot(id);
    if (slot == 0) {
        return UDEKS_LIFECYCLE_INVALID;
    }
    return slot[TASK_SLOT_WAIT];
}

unsigned char udeks_lifecycle_exit_status(unsigned char id)
{
    unsigned char *slot;

    slot = task_slot(id);
    if (slot == 0) {
        return UDEKS_LIFECYCLE_INVALID;
    }
    return slot[TASK_SLOT_EXIT];
}

unsigned char udeks_lifecycle_current(void)
{
    return udeks_lifecycle_current_private;
}

unsigned char udeks_lifecycle_runnable_count(void)
{
    unsigned char count;
    unsigned char index;

    count = 0;
    for (index = 0; index < UDEKS_LIFECYCLE_MAX_TASKS; ++index) {
        if (udeks_lifecycle_slots_private[
                index * TASK_SLOT_STRIDE + TASK_SLOT_STATE] ==
                UDEKS_LIFECYCLE_STATE_RUNNABLE ||
            udeks_lifecycle_slots_private[
                index * TASK_SLOT_STRIDE + TASK_SLOT_STATE] ==
                UDEKS_LIFECYCLE_STATE_RUNNING) {
            ++count;
        }
    }
    return count;
}

unsigned char udeks_lifecycle_defined_count(void)
{
    unsigned char count;
    unsigned char index;

    count = 0;
    for (index = 0; index < UDEKS_LIFECYCLE_MAX_TASKS; ++index) {
        if (udeks_lifecycle_slots_private[
                index * TASK_SLOT_STRIDE + TASK_SLOT_STATE] !=
                UDEKS_LIFECYCLE_STATE_FREE) {
            ++count;
        }
    }
    return count;
}

unsigned int udeks_lifecycle_switch_count(void)
{
    return switch_count;
}

unsigned char udeks_lifecycle_rejected_count(void)
{
    return udeks_lifecycle_rejected_private;
}

unsigned char udeks_lifecycle_canary_failures(void)
{
    return canary_failures;
}

void udeks_lifecycle_note_canary_failure(void)
{
    ++canary_failures;
}

#ifdef __CC65__
#pragma code-name(push, "SCHEDULER")
#endif
void udeks_lifecycle_publish(unsigned char *record)
{
    unsigned int switches;

    record[UDEKS_UTSK_MAGIC0] = 'U';
    record[UDEKS_UTSK_MAGIC1] = 'T';
    record[UDEKS_UTSK_MAGIC2] = 'S';
    record[UDEKS_UTSK_MAGIC3] = 'K';
    record[UDEKS_UTSK_ABI_MAJOR] = UDEKS_LIFECYCLE_ABI_MAJOR;
    record[UDEKS_UTSK_ABI_MINOR] = UDEKS_LIFECYCLE_ABI_MINOR;
    if (table_ready != 0) {
        record[UDEKS_UTSK_STATE] = UDEKS_LIFECYCLE_READY;
    } else {
        record[UDEKS_UTSK_STATE] = (unsigned char)(
            UDEKS_LIFECYCLE_ERROR | 1u);
    }
    record[UDEKS_UTSK_CURRENT] = udeks_lifecycle_current_private;
    record[UDEKS_UTSK_RUNNABLE] = udeks_lifecycle_runnable_count();
    record[UDEKS_UTSK_DEFINED] = udeks_lifecycle_defined_count();
    record[UDEKS_UTSK_REJECTED] = udeks_lifecycle_rejected_private;
    record[UDEKS_UTSK_CANARY] = canary_failures;
    switches = switch_count;
    record[UDEKS_UTSK_SWITCHES_LO] = (unsigned char)(switches & 0xFFu);
    record[UDEKS_UTSK_SWITCHES_HI] = (unsigned char)(switches >> 8);
    record[UDEKS_UTSK_LAST_EVENT] =
        udeks_lifecycle_last_event_private;
    record[UDEKS_UTSK_CHILD_STATE] = udeks_lifecycle_slots_private[TASK_SLOT_STRIDE + TASK_SLOT_STATE];
}
#ifdef __CC65__
#pragma code-name(pop)
#endif

unsigned char udeks_lifecycle_bootstrap(unsigned char *record)
{
    unsigned char result;

    result = udeks_lifecycle_reset();
    if (result == UDEKS_LIFECYCLE_OK) {
        result = udeks_lifecycle_create(
            1u, UDEKS_LIFECYCLE_ID_NONE,
            UDEKS_LIFECYCLE_FLAG_USER | UDEKS_LIFECYCLE_FLAG_PERSISTENT);
    }
    if (result == UDEKS_LIFECYCLE_OK) {
        result = udeks_lifecycle_apply(
            1u, UDEKS_LIFECYCLE_EVENT_ADMIT, 0u);
    }
    if (result == UDEKS_LIFECYCLE_OK) {
        result = udeks_lifecycle_apply(
            1u, UDEKS_LIFECYCLE_EVENT_DISPATCH, 0u);
    }
    udeks_lifecycle_publish(record);
    return result;
}
