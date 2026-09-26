/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/task_state.h"

#define TASK_SLOT_INVALID     0xFFu
#define TASK_TRANSITION_NONE  0xFFu

struct task_slot {
    unsigned char parent;
    unsigned char state;
    unsigned char wait_reason;
    unsigned char flags;
    unsigned char exit_status;
    unsigned char dispatches;
};

/*
 * Next state for each (current state, event) pair. Columns are events
 * ADMIT..CANCEL, so the index is event-2. CREATE is handled by allocation,
 * not by this table.
 */
static const unsigned char task_transitions[UDEKS_TASK_STATE_ZOMBIE + 1u][10] = {
    /* FREE */     { TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE },
    /* NEW */      { UDEKS_TASK_STATE_RUNNABLE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_ZOMBIE,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_ZOMBIE },
    /* RUNNABLE */ { TASK_TRANSITION_NONE, UDEKS_TASK_STATE_RUNNING,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_STOPPED,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_ZOMBIE },
    /* RUNNING */  { TASK_TRANSITION_NONE, UDEKS_TASK_STATE_RUNNING,
                     UDEKS_TASK_STATE_RUNNABLE, UDEKS_TASK_STATE_WAITING,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_STOPPED,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_ZOMBIE,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_ZOMBIE },
    /* WAITING */  { TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     UDEKS_TASK_STATE_RUNNABLE, UDEKS_TASK_STATE_STOPPED,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_ZOMBIE },
    /* STOPPED */  { TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     UDEKS_TASK_STATE_RUNNABLE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, UDEKS_TASK_STATE_ZOMBIE },
    /* ZOMBIE */   { TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     TASK_TRANSITION_NONE, TASK_TRANSITION_NONE,
                     UDEKS_TASK_STATE_FREE, TASK_TRANSITION_NONE }
};

static struct task_slot task_slots[UDEKS_TASK_MAX_TASKS];
static unsigned char current_task;
static unsigned char rejected_transitions;
static unsigned char canary_failures;
static unsigned char last_event;
static unsigned char table_ready;
static unsigned int switch_count;

static struct task_slot *task_slot(unsigned char id)
{
    if (id < 1u || id > UDEKS_TASK_MAX_TASKS) {
        return 0;
    }
    return &task_slots[id - 1u];
}

unsigned char udeks_task_state_reset(void)
{
    unsigned char index;

    for (index = 0; index < UDEKS_TASK_MAX_TASKS; ++index) {
        task_slots[index].parent = UDEKS_TASK_ID_NONE;
        task_slots[index].state = UDEKS_TASK_STATE_FREE;
        task_slots[index].wait_reason = UDEKS_TASK_WAIT_NONE;
        task_slots[index].flags = 0;
        task_slots[index].exit_status = 0;
        task_slots[index].dispatches = 0;
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
    struct task_slot *slot;

    slot = task_slot(id);
    if (slot == 0) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_ID;
    }
    if (slot->state != UDEKS_TASK_STATE_FREE) {
        ++rejected_transitions;
        return UDEKS_TASK_EXISTS;
    }
    if (parent != UDEKS_TASK_ID_NONE && task_slot(parent) == 0) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_ID;
    }

    slot->parent = parent;
    slot->state = UDEKS_TASK_STATE_NEW;
    slot->wait_reason = UDEKS_TASK_WAIT_NONE;
    slot->flags = flags;
    slot->exit_status = 0;
    slot->dispatches = 0;
    last_event = UDEKS_TASK_EVENT_CREATE;
    return UDEKS_TASK_OK;
}

unsigned char udeks_task_state_apply(
    unsigned char id, unsigned char event, unsigned char argument)
{
    struct task_slot *slot;
    unsigned char next;

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
        if (current_task == id && slot->state == UDEKS_TASK_STATE_RUNNING) {
            last_event = event;
            return UDEKS_TASK_OK;
        }
    }

    next = task_transitions[slot->state][event - 2u];
    if (next == TASK_TRANSITION_NONE) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_STATE;
    }
    if (event == UDEKS_TASK_EVENT_BLOCK &&
        (argument == UDEKS_TASK_WAIT_NONE ||
         argument > UDEKS_TASK_WAIT_TERMINAL)) {
        ++rejected_transitions;
        return UDEKS_TASK_BAD_REASON;
    }

    if (slot->state == UDEKS_TASK_STATE_RUNNING &&
        next != UDEKS_TASK_STATE_RUNNING) {
        current_task = UDEKS_TASK_ID_NONE;
    }
    if (event == UDEKS_TASK_EVENT_DISPATCH) {
        current_task = id;
        ++switch_count;
        ++slot->dispatches;
    }
    if (event == UDEKS_TASK_EVENT_EXIT) {
        slot->exit_status = argument;
    } else if (event == UDEKS_TASK_EVENT_CANCEL) {
        slot->exit_status = 0;
    }
    if (event == UDEKS_TASK_EVENT_BLOCK) {
        slot->wait_reason = argument;
    } else {
        slot->wait_reason = UDEKS_TASK_WAIT_NONE;
    }

    slot->state = next;
    last_event = event;
    return UDEKS_TASK_OK;
}

unsigned char udeks_task_state_get(unsigned char id)
{
    struct task_slot *slot;

    slot = task_slot(id);
    if (slot == 0) {
        return TASK_SLOT_INVALID;
    }
    return slot->state;
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
        if (task_slots[index].state == UDEKS_TASK_STATE_RUNNABLE ||
            task_slots[index].state == UDEKS_TASK_STATE_RUNNING) {
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
        if (task_slots[index].state != UDEKS_TASK_STATE_FREE) {
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
