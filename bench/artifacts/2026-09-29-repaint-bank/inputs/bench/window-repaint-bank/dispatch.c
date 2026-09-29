/* SPDX-License-Identifier: GPL-3.0-or-later */
/* All inputs are copied values in common RAM: no cross-bank pointers. */
#include "packet.h"
void repaint_dispatch(void)
{
    uint8_t result = UDEKS_REPAINT_INVALID;
    switch (packet.op) {
    case REPAINT_INIT: udeks_lane_init(); result = UDEKS_REPAINT_OK; break;
    case REPAINT_REQUEST: result = udeks_lane_request(&packet.damage); break;
    case REPAINT_CHANGED: result = udeks_lane_changed(&packet.damage); break;
    case REPAINT_ABORT: result = udeks_lane_abort(); break;
    case REPAINT_PEEK:
        result = udeks_lane_peek(packet.windows, packet.count, &packet.work); break;
    case REPAINT_VALIDATE: result = udeks_lane_validate(&packet.ticket); break;
    case REPAINT_ACK: result = udeks_lane_ack(&packet.ticket, packet.completion); break;
    }
    packet.result = result;
    packet.snapshot = udeks_repaint_lane;
}
