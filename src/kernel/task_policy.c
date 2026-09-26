/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/task_policy.h"
#include "udeks/task_request.h"
#include "udeks/task_state.h"

static unsigned char name_character_ok(unsigned char character)
{
    if (character >= '0' && character <= '9') {
        return 1;
    }
    if (character >= 'A' && character <= 'Z') {
        return 1;
    }
    if (character >= 'a' && character <= 'z') {
        return 1;
    }
    if (character == '.' || character == '_' ||
        character == '+' || character == '-') {
        return 1;
    }
    return 0;
}

static unsigned char child_of(unsigned char id, unsigned char caller)
{
    unsigned char state;

    state = udeks_lifecycle_get(id);
    if (state == UDEKS_LIFECYCLE_INVALID ||
        state == UDEKS_LIFECYCLE_STATE_FREE) {
        return 0;
    }
    return udeks_lifecycle_parent(id) == caller;
}

static unsigned int candidate_word(
    const unsigned char *candidate, unsigned char offset)
{
    return (unsigned int)candidate[offset] |
           ((unsigned int)candidate[offset + 1u] << 8);
}

unsigned char udeks_task_policy_validate(
    unsigned char operation, unsigned char flags, unsigned char count,
    unsigned char descriptor, const unsigned char *payload,
    unsigned char caller_id, unsigned char *task_id,
    unsigned char *status, unsigned int *ticks)
{
    unsigned char caller_state;
    unsigned char seen_child;
    unsigned char index;
    unsigned char state;
    unsigned char target_low;
    unsigned char target_high;
    unsigned int tick_value;

    *task_id = UDEKS_LIFECYCLE_ID_NONE;
    *status = 0;
    *ticks = 0;

    if (operation < UDEKS_TREQ_OP_YIELD ||
        operation > UDEKS_TREQ_OP_SPAWN) {
        return UDEKS_TREQ_ENOSYS;
    }

    caller_state = udeks_lifecycle_get(caller_id);
    if (caller_state == UDEKS_LIFECYCLE_INVALID ||
        caller_state == UDEKS_LIFECYCLE_STATE_FREE) {
        return UDEKS_TREQ_ESRCH;
    }
    if (caller_state != UDEKS_LIFECYCLE_STATE_RUNNING ||
        udeks_lifecycle_current() != caller_id) {
        return UDEKS_TREQ_EINVAL;
    }
    if (descriptor != 0) {
        return UDEKS_TREQ_EINVAL;
    }

    if (operation == UDEKS_TREQ_OP_YIELD) {
        if (flags != 0 || count != UDEKS_TREQ_YIELD_COUNT) {
            return UDEKS_TREQ_EINVAL;
        }
        return 0;
    }

    if (operation == UDEKS_TREQ_OP_EXIT) {
        if (flags != 0 || count != UDEKS_TREQ_EXIT_COUNT) {
            return UDEKS_TREQ_EINVAL;
        }
        *task_id = caller_id;
        *status = payload[UDEKS_TREQ_EXIT_STATUS];
        return 0;
    }

    if (operation == UDEKS_TREQ_OP_WAITPID) {
        if ((flags & (unsigned char)~UDEKS_TREQ_WAITPID_NOHANG) != 0 ||
            count != UDEKS_TREQ_WAITPID_COUNT) {
            return UDEKS_TREQ_EINVAL;
        }
        target_low = payload[UDEKS_TREQ_TASK_ID_LOW];
        target_high = payload[UDEKS_TREQ_TASK_ID_HIGH];
        if (target_high != 0) {
            return UDEKS_TREQ_ECHILD;
        }
        if (target_low != 0) {
            if (target_low == caller_id ||
                !child_of(target_low, caller_id)) {
                return UDEKS_TREQ_ECHILD;
            }
            *task_id = target_low;
            state = udeks_lifecycle_get(target_low);
            if (state == UDEKS_LIFECYCLE_STATE_ZOMBIE) {
                *status = udeks_lifecycle_exit_status(target_low);
            }
            return 0;
        }
        /* Selector 0 waits for any child. A zombie is reaped first; with no
         * zombie the selector stays 0 so any child exit can wake the wait. */
        seen_child = 0;
        for (index = 1; index <= UDEKS_LIFECYCLE_MAX_TASKS; ++index) {
            if (!child_of(index, caller_id)) {
                continue;
            }
            if (udeks_lifecycle_get(index) == UDEKS_LIFECYCLE_STATE_ZOMBIE) {
                *task_id = index;
                *status = udeks_lifecycle_exit_status(index);
                return 0;
            }
            seen_child = 1;
        }
        if (seen_child != 0) {
            *task_id = UDEKS_LIFECYCLE_ID_NONE;
            return 0;
        }
        return UDEKS_TREQ_ECHILD;
    }

    if (operation == UDEKS_TREQ_OP_SLEEP) {
        if (flags != 0 || count != UDEKS_TREQ_SLEEP_COUNT) {
            return UDEKS_TREQ_EINVAL;
        }
        tick_value = (unsigned int)payload[UDEKS_TREQ_SLEEP_TICKS_LOW];
        tick_value |= (unsigned int)payload[UDEKS_TREQ_SLEEP_TICKS_HIGH] << 8;
        if (tick_value == 0 || tick_value > UDEKS_TREQ_SLEEP_TICKS_MAX) {
            return UDEKS_TREQ_EINVAL;
        }
        *ticks = tick_value;
        return 0;
    }

    if (operation == UDEKS_TREQ_OP_CANCEL) {
        if (flags != 0 || count != UDEKS_TREQ_CANCEL_COUNT) {
            return UDEKS_TREQ_EINVAL;
        }
        target_low = payload[UDEKS_TREQ_TASK_ID_LOW];
        target_high = payload[UDEKS_TREQ_TASK_ID_HIGH];
        if (target_low == 0 && target_high == 0) {
            return UDEKS_TREQ_EINVAL;
        }
        if (target_high == 0 && target_low == caller_id) {
            return UDEKS_TREQ_EINVAL;
        }
        if (target_high != 0) {
            return UDEKS_TREQ_ESRCH;
        }
        state = udeks_lifecycle_get(target_low);
        if (state == UDEKS_LIFECYCLE_INVALID ||
            state == UDEKS_LIFECYCLE_STATE_FREE ||
            state == UDEKS_LIFECYCLE_STATE_ZOMBIE ||
            udeks_lifecycle_parent(target_low) != caller_id) {
            return UDEKS_TREQ_ESRCH;
        }
        *task_id = target_low;
        *status = payload[UDEKS_TREQ_CANCEL_STATUS];
        return 0;
    }

    if (operation == UDEKS_TREQ_OP_SPAWN) {
        if (flags != 0 || count != UDEKS_TREQ_SPAWN_COUNT) {
            return UDEKS_TREQ_EINVAL;
        }
        target_low = payload[UDEKS_TREQ_SPAWN_NAME_LENGTH];
        if (target_low == 0 || target_low > UDEKS_TREQ_SPAWN_NAME_MAX) {
            return UDEKS_TREQ_EINVAL;
        }
        for (index = 0; index < target_low; ++index) {
            if (!name_character_ok(
                    payload[UDEKS_TREQ_SPAWN_NAME + index])) {
                return UDEKS_TREQ_EINVAL;
            }
        }
        for (index = target_low; index < UDEKS_TREQ_SPAWN_NAME_MAX; ++index) {
            if (payload[UDEKS_TREQ_SPAWN_NAME + index] != 0) {
                return UDEKS_TREQ_EINVAL;
            }
        }
        return 0;
    }

    return UDEKS_TREQ_ENOSYS;
}

unsigned char udeks_task_policy_validate_spawn_candidate(
    const unsigned char *candidate,
    const unsigned char *reserved, unsigned char reserved_count)
{
    unsigned int image_base;
    unsigned int image_size;
    unsigned int bss_size;
    unsigned int entry;
    unsigned int stack_base;
    unsigned int stack_size;
    unsigned int image_last;
    unsigned int stack_last;
    unsigned int region_base;
    unsigned int region_size;
    unsigned int region_last;
    unsigned char index;

    if (candidate[UDEKS_TASK_CANDIDATE_MAGIC] != 'U' ||
        candidate[UDEKS_TASK_CANDIDATE_MAGIC + 1u] != 'D' ||
        candidate[UDEKS_TASK_CANDIDATE_MAGIC + 2u] != 'E' ||
        candidate[UDEKS_TASK_CANDIDATE_MAGIC + 3u] != 'X') {
        return UDEKS_TREQ_ENOEXEC;
    }
    if (candidate[UDEKS_TASK_CANDIDATE_MAJOR] !=
            UDEKS_TASK_POLICY_MAJOR_UDEX) {
        return UDEKS_TREQ_ENOEXEC;
    }
    if (candidate[UDEKS_TASK_CANDIDATE_MINOR] >
            UDEKS_TASK_POLICY_MINOR_UDEX) {
        return UDEKS_TREQ_ENOEXEC;
    }
    if (candidate[UDEKS_TASK_CANDIDATE_CPU] != UDEKS_TASK_POLICY_CPU_8502) {
        return UDEKS_TREQ_ENOEXEC;
    }
    /* Valid flags are 0, persistent ($01), and managed ($02); unknown bits
     * and the combined $03 value are rejected. */
    if (candidate[UDEKS_TASK_CANDIDATE_FLAGS] >
            UDEKS_TASK_POLICY_FLAG_MANAGED) {
        return UDEKS_TREQ_ENOEXEC;
    }

    image_base = candidate_word(candidate, UDEKS_TASK_CANDIDATE_IMAGE_BASE);
    image_size = candidate_word(candidate, UDEKS_TASK_CANDIDATE_IMAGE_SIZE);
    bss_size = candidate_word(candidate, UDEKS_TASK_CANDIDATE_BSS_SIZE);
    entry = candidate_word(candidate, UDEKS_TASK_CANDIDATE_ENTRY);
    stack_base = candidate_word(candidate, UDEKS_TASK_CANDIDATE_STACK_BASE);
    stack_size = candidate_word(candidate, UDEKS_TASK_CANDIDATE_STACK_SIZE);

    /* All range math uses inclusive last addresses so a valid range may end
     * exactly at $FFFF and the checks are identical on cc65 and the host. */
    if (image_size == 0) {
        return UDEKS_TREQ_ENOEXEC;
    }
    if (image_size - 1u > 0xFFFFu - image_base) {
        return UDEKS_TREQ_ENOMEM;
    }
    image_last = image_base + image_size - 1u;
    if (entry < image_base || entry > image_last) {
        return UDEKS_TREQ_ENOEXEC;
    }
    if (bss_size != 0) {
        if (bss_size > 0xFFFFu - image_last) {
            return UDEKS_TREQ_ENOMEM;
        }
        image_last = image_last + bss_size;
    }

    if (stack_size < UDEKS_TASK_POLICY_STACK_MIN) {
        return UDEKS_TREQ_EINVAL;
    }
    if (stack_size - 1u > 0xFFFFu - stack_base) {
        return UDEKS_TREQ_EINVAL;
    }
    stack_last = stack_base + stack_size - 1u;
    if (stack_base <= image_last && image_base <= stack_last) {
        return UDEKS_TREQ_EINVAL;
    }

    for (index = 0; index < reserved_count; ++index) {
        const unsigned char *region =
            reserved + ((unsigned int)index * UDEKS_TASK_POLICY_RESERVED_SIZE);

        region_base = (unsigned int)region[0] |
                      ((unsigned int)region[1] << 8);
        region_size = (unsigned int)region[2] |
                      ((unsigned int)region[3] << 8);
        if (region_size == 0) {
            continue;
        }
        if (region_size - 1u > 0xFFFFu - region_base) {
            region_last = 0xFFFFu;
        } else {
            region_last = region_base + region_size - 1u;
        }
        if (image_base <= region_last && region_base <= image_last) {
            return UDEKS_TREQ_ENOMEM;
        }
        if (stack_base <= region_last && region_base <= stack_last) {
            return UDEKS_TREQ_ENOMEM;
        }
    }

    return 0;
}
