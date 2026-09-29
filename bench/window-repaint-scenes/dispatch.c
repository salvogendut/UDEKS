/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Local views die before bank return. No persistent scene or pointer added. */
#include "packet.h"
#include "udeks/window.h"
static uint8_t peek_scenes(void)
{
    struct udeks_repaint_window views[4];
    register const struct repaint_scene *scene;
    register struct udeks_repaint_window *view;
    uint8_t i, count=0;
    if (packet.count!=REPAINT_SCENE_FORMAT || packet.reserved[0] || packet.reserved[1] ||
        packet.reserved[2] || packet.reserved[3]) return UDEKS_REPAINT_INVALID;
    scene=packet.scenes;view=views;
    for(i=0;i<4u;++i,++scene) {
        if (!scene->rank || !(scene->flags & UDEKS_WINDOW_FLAG_VISIBLE)) continue;
        if (scene->rank>4u || scene->width<16u || scene->width>320u ||
            scene->height<=17u || scene->height>200u ||
            scene->x>320u-scene->width || scene->y>200u-scene->height)
            return UDEKS_REPAINT_INVALID;
        view->bounds.left=scene->x;view->bounds.right=scene->x+scene->width;
        view->bounds.top=scene->y;view->bounds.bottom=scene->y+scene->height;
        view->handle=i+1u;view->rank=scene->rank;view->flags=UDEKS_REPAINT_VISIBLE;
        ++view;++count;
    }
    return udeks_lane_peek(views,count,&packet.work);
}
void repaint_dispatch(void)
{
    uint8_t result=UDEKS_REPAINT_INVALID;
    REPAINT_PACKET_CHECK();
    switch(packet.op) {
    case REPAINT_INIT:udeks_lane_init();result=UDEKS_REPAINT_OK;break;
    case REPAINT_REQUEST:result=udeks_lane_request(&packet.damage);break;
    case REPAINT_CHANGED:result=udeks_lane_changed(&packet.damage);break;
    case REPAINT_ABORT:result=udeks_lane_abort();break;
    case REPAINT_PEEK:result=peek_scenes();break;
    case REPAINT_VALIDATE:result=udeks_lane_validate(&packet.ticket);break;
    case REPAINT_ACK:result=udeks_lane_ack(&packet.ticket,packet.completion);break;
    }
    packet.result=result;packet.snapshot=udeks_repaint_lane;
}
