/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private marshalling cost/proof, not a public UAPP gate. Caller holds the
 * serialized graphics lease, owns a local work copy, and stays in kernel I/O.
 * No pointer persists in the shared packet; VIC/cache may overwrite it later.
 */
#include "../window-repaint-bank/packet.h"
extern unsigned char private_repaint_policy_call(void);
static unsigned char receipt(const struct udeks_repaint_lane_ticket *ticket,
    unsigned char completion, unsigned char op)
{
    if (!ticket) return UDEKS_REPAINT_INVALID;
    packet.ticket = *ticket;
    packet.completion = completion;
    packet.op = op;
    return private_repaint_policy_call();
}
unsigned char repaint_receipt_validate(const struct udeks_repaint_lane_ticket *ticket)
{
    return receipt(ticket, 0, REPAINT_VALIDATE);
}
unsigned char repaint_receipt_ack(const struct udeks_repaint_lane_ticket *ticket,
    unsigned char result)
{
    return receipt(ticket, result, REPAINT_ACK);
}
