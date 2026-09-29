#include "udeks/window.h"
/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private prototype 0.2. Geometry VALUES only, never app/bank-0 pointers. */
#ifndef REPAINT_SCENE_PACKET_H
#define REPAINT_SCENE_PACKET_H
#include <stddef.h>
#include "udeks/repaint_lane.h"
#define REPAINT_INIT 0u
#define REPAINT_REQUEST 1u
#define REPAINT_CHANGED 2u
#define REPAINT_ABORT 3u
#define REPAINT_PEEK 4u
#define REPAINT_VALIDATE 5u
#define REPAINT_ACK 6u
#define REPAINT_SCENE_FORMAT 0x84u /* old view-count <=4 cannot pass */
#ifdef REPAINT_HOST
#pragma pack(push, 1)
#endif
struct repaint_scene {
    uint8_t poison, flags;
    uint16_t x;
    uint8_t y;
    uint16_t width;
    uint8_t height, rank;
};
struct repaint_packet {
    uint8_t op, count, completion, result;
    struct udeks_repaint_rect damage;
    struct udeks_repaint_lane_ticket ticket;
    struct repaint_scene scenes[4];
    uint8_t reserved[4];
    struct udeks_repaint_lane_work work;
    struct udeks_repaint_lane snapshot; /* observation only, not authority */
};
#ifdef REPAINT_HOST
#pragma pack(pop)
extern struct repaint_packet repaint_packet;
#define packet repaint_packet
#else
#define packet (*(struct repaint_packet *)0xF780u)
#endif
#define REPAINT_PACKET_CHECK() ((void)0)
#ifndef __CC65__
typedef char scene_size[(sizeof(struct repaint_scene)==8)?1:-1];
typedef char packet_size[(sizeof(struct repaint_packet)==82)?1:-1];
typedef char ticket_offset[(offsetof(struct repaint_packet,ticket)==10)?1:-1];
typedef char work_offset[(offsetof(struct repaint_packet,work)==52)?1:-1];
typedef char result_offset[(offsetof(struct repaint_packet,result)==3)?1:-1];
typedef char snapshot_offset[(offsetof(struct repaint_packet,snapshot)==64)?1:-1];
#endif
void repaint_dispatch(void);
#endif

struct udeks_window {
    unsigned char flags;
    unsigned int x;
    unsigned char y;
    unsigned int width;
    unsigned char height;
    unsigned char z;
    const unsigned char *title;
    udeks_window_paint_fn paint;
    udeks_window_close_fn close;
};
const unsigned char layout[] = {offsetof(struct udeks_window,flags),offsetof(struct udeks_window,x),offsetof(struct udeks_window,y),offsetof(struct udeks_window,width),offsetof(struct udeks_window,height),offsetof(struct udeks_window,z),offsetof(struct udeks_window,title),sizeof(struct repaint_scene),sizeof(struct repaint_packet),offsetof(struct repaint_packet,ticket),offsetof(struct repaint_packet,work),offsetof(struct repaint_packet,result),offsetof(struct repaint_packet,snapshot)};
