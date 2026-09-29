/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Same command stream on the packed host oracle and the real cc65 caller. */
#include <string.h>
#include "packet.h"
#ifdef REPAINT_HOST
#include <stdio.h>
struct repaint_packet repaint_packet;
#else
#include "expected.h"
#define V(a) (*(volatile uint8_t *)(a))
#define RECORD 0x7FC0u
extern void runtime_install(void), runtime_irq_start(void), runtime_irq_stop(void);
extern void runtime_check_memory(void);
extern uint8_t runtime_call(void);
extern uint32_t runtime_irq_count;
extern uint16_t runtime_call_count;
extern uint8_t runtime_irq_bad, runtime_zp_bad, runtime_hw_bad, runtime_flags_bad;
extern uint8_t runtime_sw_bad, runtime_guard_bad, runtime_ush_bad, runtime_low_water;
extern uint8_t runtime_seen_flags;
#endif
static uint16_t calls;
static uint8_t failure, trace_low = 0x57u, trace_high = 0x13u;
static void check(uint8_t ok, uint8_t code) { if (!ok && !failure) failure = code; }
static uint8_t call(uint8_t op)
{
    uint8_t i, returned;
    const uint8_t *bytes = (const uint8_t *)&packet;
    packet.op = op;
#ifdef REPAINT_HOST
    repaint_dispatch();
#else
    returned = runtime_call();
    check(returned == packet.result, 1);
#endif
    ++calls;
    /* Cheap non-cryptographic stream checksum, not an equivalence proof by
     * itself. Explicit semantic checks and fault controls are also required. */
    for (i = 0; i < sizeof(packet); ++i) {
        trace_low += bytes[i];
        trace_high += trace_low;
    }
    return packet.result;
}
static void scene(uint8_t round)
{
    packet.count = 2;
    packet.windows[0].bounds.left = 8;
    packet.windows[0].bounds.right = 120;
    packet.windows[0].bounds.top = 5;
    packet.windows[0].bounds.bottom = 65;
    packet.windows[0].handle = 1;
    packet.windows[0].rank = 1;
    packet.windows[0].flags = UDEKS_REPAINT_VISIBLE;
    packet.windows[1].bounds.left = 70;
    packet.windows[1].bounds.right = 190;
    packet.windows[1].bounds.top = 30;
    packet.windows[1].bounds.bottom = 90;
    packet.windows[1].handle = 2;
    packet.windows[1].rank = 2;
    packet.windows[1].flags = UDEKS_REPAINT_VISIBLE |
        ((round & 1u) ? UDEKS_REPAINT_RETAINED : 0u);
    packet.damage.left = round;
    packet.damage.right = 200u + round;
    packet.damage.top = 0;
    packet.damage.bottom = 80;
}
static void exercise(void)
{
    uint8_t round, invalidated, queued, result;
    uint16_t budget;
    struct udeks_repaint_lane before;
    memset(&packet, 0, sizeof(packet));
    check(sizeof(packet) == 82 && sizeof(packet.windows[0]) == 9, 2);
    check(call(REPAINT_INIT) == UDEKS_REPAINT_OK, 3);
    before = packet.snapshot;
    check(call(255) == UDEKS_REPAINT_INVALID, 4);
    check(memcmp(&before, &packet.snapshot, sizeof(before)) == 0, 5);
    check(call(REPAINT_REQUEST) == UDEKS_REPAINT_INVALID, 6);
    check(memcmp(&before, &packet.snapshot, sizeof(before)) == 0, 7);
    for (round = 0; round < 8; ++round) {
        scene(round);
        check(call(REPAINT_CHANGED) == UDEKS_REPAINT_OK, 8);
        invalidated = queued = 0;
        for (budget = 0; budget < 500; ++budget) {
            result = call(REPAINT_PEEK);
            if (result == UDEKS_REPAINT_IDLE) break;
            if (result == UDEKS_REPAINT_YIELD) continue;
            if (result != UDEKS_REPAINT_OK) {
                check(0, 9);
                break;
            }
            packet.ticket = packet.work.ticket;
            check(call(REPAINT_VALIDATE) == UDEKS_REPAINT_OK, 10);
            if (!queued) {
                check(call(REPAINT_REQUEST) == UDEKS_REPAINT_OK, 11);
                check(call(REPAINT_VALIDATE) == UDEKS_REPAINT_OK, 12);
                queued = 1;
            }
            if (!invalidated && packet.ticket.phase == UDEKS_REPAINT_CHROME &&
                    packet.ticket.cursor == 1) {
                check(call(REPAINT_CHANGED) == UDEKS_REPAINT_OK, 13);
                packet.windows[0].bounds.left += 2u; /* fence BEFORE mutation */
                before = packet.snapshot;
                check(call(REPAINT_VALIDATE) == UDEKS_REPAINT_STALE, 14);
                check(call(REPAINT_ACK) == UDEKS_REPAINT_STALE, 15);
                check(memcmp(&before, &packet.snapshot, sizeof(before)) == 0, 16);
                invalidated = 1;
                continue;
            }
            packet.completion = packet.ticket.phase != UDEKS_REPAINT_CLEAR &&
                packet.ticket.cursor < (packet.ticket.phase == UDEKS_REPAINT_COMMIT ? 1u : 2u)
                ? UDEKS_REPAINT_MORE : UDEKS_REPAINT_DONE;
            check(call(REPAINT_ACK) == UDEKS_REPAINT_OK, 17);
        }
        check(budget < 500 && invalidated && queued, 18);
        check(call(REPAINT_REQUEST) == UDEKS_REPAINT_OK, 19);
        packet.count = 5;
        before = packet.snapshot;
        check(call(REPAINT_PEEK) == UDEKS_REPAINT_INVALID, 20);
        check(memcmp(&before, &packet.snapshot, sizeof(before)) == 0, 21);
        packet.count = 2;
        check(call(REPAINT_PEEK) == UDEKS_REPAINT_OK, 22);
        packet.ticket = packet.work.ticket;
        check(call(REPAINT_ABORT) == UDEKS_REPAINT_OK, 23);
        check(call(REPAINT_VALIDATE) == UDEKS_REPAINT_STALE, 24);
        check(call(REPAINT_ACK) == UDEKS_REPAINT_STALE, 25);
        check(call(REPAINT_PEEK) == UDEKS_REPAINT_IDLE, 26);
    }
}
int main(void)
{
    uint16_t trace;
#ifdef REPAINT_HOST
    exercise();
    trace = trace_low | ((uint16_t)trace_high << 8);
    printf("%u %u %u\n", calls, trace, failure);
    return failure != 0;
#else
    uint16_t i;
    for (i = 0; i < 8096u; ++i) V(RECORD + i) = 0;
    V(RECORD) = 'R'; V(RECORD+1) = 'B'; V(RECORD+2) = 'N'; V(RECORD+3) = 'K';
    V(RECORD+4) = 1; V(RECORD+5) = 1;
    runtime_install(); runtime_irq_start();
    exercise();
    trace = trace_low | ((uint16_t)trace_high << 8);
    check(calls == EXPECTED_CALLS && trace == EXPECTED_TRACE, 27);
    runtime_irq_stop(); runtime_check_memory();
    V(RECORD+7) = failure;
    V(RECORD+8) = calls; V(RECORD+9) = calls >> 8;
    V(RECORD+10) = trace; V(RECORD+11) = trace >> 8;
    for (i = 0; i < 4; ++i) V(RECORD+12+i) = runtime_irq_count >> (i * 8u);
    V(RECORD+16) = runtime_irq_bad; V(RECORD+17) = runtime_zp_bad;
    V(RECORD+18) = runtime_hw_bad; V(RECORD+19) = runtime_flags_bad;
    V(RECORD+20) = runtime_sw_bad; V(RECORD+21) = runtime_guard_bad;
    V(RECORD+22) = runtime_ush_bad; V(RECORD+23) = runtime_low_water;
    V(RECORD+24) = runtime_seen_flags;
    check(runtime_call_count == calls, 28);
    V(RECORD+7) = failure;
    V(RECORD+5) = 2;
    return 0;
#endif
}
