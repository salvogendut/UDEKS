/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/repaint_lane.h"
const uint8_t udeks_lane_layout[] = {
    sizeof(struct udeks_repaint_lane), sizeof(struct udeks_repaint_lane_ticket),
    sizeof(struct udeks_repaint_lane_work), sizeof(struct udeks_repaint_window)
};
