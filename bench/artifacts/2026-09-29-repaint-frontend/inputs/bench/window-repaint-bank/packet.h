/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private marshalling experiment. Host oracle compiles with -fpack-struct=1. */
#include "udeks/repaint_lane.h"
#define REPAINT_INIT 0u
#define REPAINT_REQUEST 1u
#define REPAINT_CHANGED 2u
#define REPAINT_ABORT 3u
#define REPAINT_PEEK 4u
#define REPAINT_VALIDATE 5u
#define REPAINT_ACK 6u
struct repaint_packet {
    uint8_t op, count, completion, result;
    struct udeks_repaint_rect damage;
    struct udeks_repaint_lane_ticket ticket;
    struct udeks_repaint_window windows[4];
    struct udeks_repaint_lane_work work;
    struct udeks_repaint_lane snapshot; /* diagnostic response; not authority */
};
#ifdef REPAINT_HOST
extern struct repaint_packet repaint_packet;
#define packet repaint_packet
#else
#define packet (*(struct repaint_packet *)0xF780u)
#endif
void repaint_dispatch(void);
