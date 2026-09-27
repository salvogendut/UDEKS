/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TASK_POLL_POLICY_H
#define UDEKS_TASK_POLL_POLICY_H

/* Experimental, host-tested specification for docs/EVENT-WAITS.md.
 * Compile-only on cc65: NOT a published syscall or a resident component.
 * Keep these constants separate from the advertised Task Request ABI 0.3.
 */
#define UDEKS_POLL_POLICY_ABI_MAJOR       0u
#define UDEKS_POLL_POLICY_ABI_MINOR       4u
#define UDEKS_POLL_POLICY_OPERATION      16u
#define UDEKS_POLL_POLICY_COUNT          4u
#define UDEKS_POLL_POLICY_READABLE       0x0001u
#define UDEKS_POLL_POLICY_TIMEOUT_MAX    600u
#define UDEKS_POLL_POLICY_FOREVER        0xFFFFu

/* Offsets relative to the existing UDEKS_TREQ_PAYLOAD. On completion the
 * mask is replaced by the ready mask; both timeout bytes are preserved.
 */
#define UDEKS_POLL_POLICY_MASK_LOW        0u
#define UDEKS_POLL_POLICY_MASK_HIGH       1u
#define UDEKS_POLL_POLICY_TIMEOUT_LOW     2u
#define UDEKS_POLL_POLICY_TIMEOUT_HIGH    3u

/* Decision values are private, not request states or syscall return values.
 * READY completes with result 1/mask 1; EXPIRED with result 0/mask 0.
 * Both completions have errno 0. WAIT requires private snapshot ownership.
 */
#define UDEKS_POLL_POLICY_WAIT            0u
#define UDEKS_POLL_POLICY_READY           1u
#define UDEKS_POLL_POLICY_EXPIRED         2u

/* Validate a complete, readable UDEKS_TASK_REQUEST_SIZE-byte request.
 * request and timeout must be non-null and must not alias. Precedence:
 *   EPROTO: wrong magic/major, future minor, or non-request state;
 *   ENOSYS: not POLL, or POLL submitted by an older minor;
 *   ESRCH: undefined caller;
 *   EINVAL: caller not current/RUNNING;
 *   EBADF: descriptor other than stdin;
 *   EINVAL: flags, count, mask, or timeout malformed.
 * Success writes only *timeout. Rejection leaves even that output unchanged.
 * Neither path mutates the request, task table, or lifecycle counters.
 */
unsigned char udeks_poll_policy_validate(
    const unsigned char *request, unsigned char caller_id,
    unsigned int *timeout);

/* Pure level-triggered readiness decision: no input consumption or task
 * mutation. timeout must already be validated. now/deadline are 16-bit
 * logical ticks; deadline is (registration_tick + timeout) modulo 65536 for
 * finite waits. The producer must check finite waits within half a clock
 * cycle (32768 ticks) of their deadline. Explicit masking gives identical
 * arithmetic on the host and cc65. Zero/FOREVER ignore deadline; readiness
 * wins a timeout tie. Lifecycle/snapshot ownership is the caller's job.
 */
unsigned char udeks_poll_policy_decide(
    unsigned char readable, unsigned int timeout,
    unsigned int now, unsigned int deadline);

#endif
