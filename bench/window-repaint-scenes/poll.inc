/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Exactly the value-only prefix, never a whole window or its trailing pointers.
 * Host assertions and a compiler-emitted target layout sidecar gate the copy. */
#include <string.h>
#ifndef __CC65__
typedef char prefix_flags[(offsetof(struct udeks_window,flags)==0)?1:-1];
typedef char prefix_x[(offsetof(struct udeks_window,x)==1)?1:-1];
typedef char prefix_y[(offsetof(struct udeks_window,y)==3)?1:-1];
typedef char prefix_width[(offsetof(struct udeks_window,width)==4)?1:-1];
typedef char prefix_height[(offsetof(struct udeks_window,height)==6)?1:-1];
typedef char prefix_rank[(offsetof(struct udeks_window,z)==7)?1:-1];
typedef char prefix_end[(offsetof(struct udeks_window,title)==8)?1:-1];
#endif
unsigned char repaint_frontend_poll(unsigned char lease,
    struct udeks_repaint_lane_work *output)
{
    register const struct udeks_window *window;
    register struct repaint_scene *scene;
    unsigned char remaining, status;
    REPAINT_PACKET_CHECK();
    if (!output) return UDEKS_REPAINT_INVALID;
    if (!repaint_frontend_allowed(lease) || dragging_handle!=UDEKS_WINDOW_NONE)
        return REPAINT_FRONTEND_DEFERRED;
    window=windows;scene=packet.scenes;
    remaining=4;
    do { memcpy(scene,window,8);++window;++scene; } while(--remaining);
    packet.count=REPAINT_SCENE_FORMAT;
    packet.reserved[0]=packet.reserved[1]=packet.reserved[2]=packet.reserved[3]=0;
    packet.op=REPAINT_PEEK;
    status=private_repaint_policy_call();
    if (status!=UDEKS_REPAINT_OK) return status;
    *output=packet.work;
    return lane_raster_step(output);
}
