/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Actual target struct sizes, not host ctypes alignment assumptions. */
#include "udeks/window_repaint.h"
const uint8_t udeks_repaint_layout_sizes[] = {
    sizeof(struct udeks_repaint_job), sizeof(struct udeks_repaint_ticket),
    sizeof(struct udeks_repaint_work), sizeof(struct udeks_repaint_window)
};
