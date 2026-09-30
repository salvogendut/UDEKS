/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/task_poll_policy.h"
#include "udeks/task_request.h"
#include "udeks/task_state.h"

unsigned char udeks_poll_policy_validate(
    const unsigned char *request, unsigned char caller_id,
    unsigned int *timeout)
{
    unsigned char state;
    unsigned int value;

    if (request[UDEKS_TREQ_MAGIC0] != 'U' ||
        request[UDEKS_TREQ_MAGIC1] != 'T' ||
        request[UDEKS_TREQ_MAGIC2] != 'R' ||
        request[UDEKS_TREQ_MAGIC3] != 'Q' ||
        request[UDEKS_TREQ_MAJOR] != UDEKS_POLL_POLICY_ABI_MAJOR ||
        request[UDEKS_TREQ_MINOR] > UDEKS_TASK_REQUEST_ABI_MINOR ||
        request[UDEKS_TREQ_STATE] != UDEKS_TREQ_STATE_REQUEST) {
        return UDEKS_TREQ_EPROTO;
    }
    if (request[UDEKS_TREQ_OPERATION] != UDEKS_POLL_POLICY_OPERATION ||
        request[UDEKS_TREQ_MINOR] < UDEKS_POLL_POLICY_ABI_MINOR) {
        return UDEKS_TREQ_ENOSYS;
    }

    state = udeks_lifecycle_get(caller_id);
    if (state == UDEKS_LIFECYCLE_INVALID ||
        state == UDEKS_LIFECYCLE_STATE_FREE) {
        return UDEKS_TREQ_ESRCH;
    }
    if (state != UDEKS_LIFECYCLE_STATE_RUNNING ||
        udeks_lifecycle_current() != caller_id) {
        return UDEKS_TREQ_EINVAL;
    }
    if (request[UDEKS_TREQ_DESCRIPTOR] != 0) {
        return UDEKS_TREQ_EBADF;
    }
    if (request[UDEKS_TREQ_FLAGS] != 0 ||
        request[UDEKS_TREQ_COUNT] != UDEKS_POLL_POLICY_COUNT ||
        request[UDEKS_TREQ_PAYLOAD + UDEKS_POLL_POLICY_MASK_LOW] !=
            UDEKS_POLL_POLICY_READABLE ||
        request[UDEKS_TREQ_PAYLOAD + UDEKS_POLL_POLICY_MASK_HIGH] != 0) {
        return UDEKS_TREQ_EINVAL;
    }
    value = (unsigned int)request[
        UDEKS_TREQ_PAYLOAD + UDEKS_POLL_POLICY_TIMEOUT_LOW];
    value |= (unsigned int)request[
        UDEKS_TREQ_PAYLOAD + UDEKS_POLL_POLICY_TIMEOUT_HIGH] << 8;
    if (value > UDEKS_POLL_POLICY_TIMEOUT_MAX &&
        value != UDEKS_POLL_POLICY_FOREVER) {
        return UDEKS_TREQ_EINVAL;
    }
    *timeout = value;
    return 0;
}

unsigned char udeks_poll_policy_decide(
    unsigned char readable, unsigned int timeout,
    unsigned int now, unsigned int deadline)
{
    if (readable != 0) {
        return UDEKS_POLL_POLICY_READY;
    }
    if (timeout == UDEKS_POLL_POLICY_FOREVER) {
        return UDEKS_POLL_POLICY_WAIT;
    }
    if (timeout == 0 || ((now - deadline) & 0xFFFFu) < 0x8000u) {
        return UDEKS_POLL_POLICY_EXPIRED;
    }
    return UDEKS_POLL_POLICY_WAIT;
}
