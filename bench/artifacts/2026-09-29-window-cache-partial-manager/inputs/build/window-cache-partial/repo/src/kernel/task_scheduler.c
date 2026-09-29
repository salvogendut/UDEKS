/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/task_scheduler.h"
#include "udeks/task_state.h"

#ifdef __CC65__
#pragma code-name(push, "SCHEDULER")
#endif
unsigned char udeks_scheduler_select_next(unsigned char after_id)
{
    unsigned char remaining;

    remaining = UDEKS_LIFECYCLE_MAX_TASKS;
    while (remaining != 0) {
        ++after_id;
        if (after_id > UDEKS_LIFECYCLE_MAX_TASKS) {
            after_id = 1u;
        }
        if (udeks_lifecycle_get(after_id) ==
                UDEKS_LIFECYCLE_STATE_RUNNABLE) {
            return after_id;
        }
        --remaining;
    }
    return UDEKS_SCHEDULER_NO_TASK;
}
#ifdef __CC65__
#pragma code-name(pop)
#endif
