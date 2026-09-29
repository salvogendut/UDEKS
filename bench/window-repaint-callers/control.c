/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private measurement only. Caller must own a serialized graphics lease.
 * This samples the EXISTING damage box and charges conversion to the lane
 * record. It neither fences a manager mutation nor installs a provider.
 */
#include "udeks/repaint_lane.h"
extern unsigned int damage_left,damage_right;
extern unsigned char damage_top,damage_bottom;
extern unsigned char repaint_frontend_control(unsigned char op,
    const struct udeks_repaint_rect *damage,unsigned char lease);
unsigned char repaint_control_damage(unsigned char op,unsigned char lease)
{
    struct udeks_repaint_rect rect;
    rect.left=damage_left;
    rect.right=damage_right;
    rect.top=damage_top;
    rect.bottom=damage_bottom;
    return repaint_frontend_control(op,&rect,lease);
}
