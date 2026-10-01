/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_WINDOW_H
#define UDEKS_WINDOW_H

#define UDEKS_WINDOW_STATUS_BASE          0xF240u
#define UDEKS_WINDOW_STATUS_SIZE          32u

#define UDEKS_WINDOW_READY                2u
#define UDEKS_WINDOW_ERROR                0x80u

#define UDEKS_WINDOW_OK                   0u
#define UDEKS_WINDOW_INVALID              1u
#define UDEKS_WINDOW_FULL                 2u

#define UDEKS_WINDOW_NONE                 0u
#define UDEKS_WINDOW_MAX                  4u

#define UDEKS_WINDOW_FLAG_VISIBLE         0x01u
#define UDEKS_WINDOW_FLAG_MOVABLE         0x02u
#define UDEKS_WINDOW_FLAG_CLOSABLE        0x04u
#define UDEKS_WINDOW_FLAG_RESIZABLE       0x08u
#define UDEKS_WINDOW_FLAG_FIXED_SIZE      0x10u

#define UDEKS_WINDOW_SURFACE_BITMAP       1u
#define UDEKS_WINDOW_TITLE_HEIGHT         13u

typedef void (*udeks_window_paint_fn)(unsigned char handle);
typedef void (*udeks_window_close_fn)(unsigned char handle);

unsigned char udeks_window_manager_start(void);
unsigned char udeks_window_manager_poll(void);
unsigned char udeks_window_manager_stop(void);
void udeks_window_manager_reset(void);

unsigned char udeks_window_create(
    unsigned char owner, unsigned char surface, unsigned char flags,
    unsigned int x, unsigned char y, unsigned int width,
    unsigned char height, const unsigned char *title,
    udeks_window_paint_fn paint, udeks_window_close_fn close);
unsigned char udeks_window_destroy(unsigned char handle);
unsigned char udeks_window_repaint(unsigned char handle);
unsigned char udeks_window_begin_paint(unsigned char handle);
void udeks_window_end_paint(void);
/* UAPP 0.3 optional notification: the caller has finished its whole image.
 * Only an undragged, visible, topmost bitmap is eligible. This is NOT implied
 * by end_paint, which may finish just one incremental batch. Painting or
 * compositor damage withdraws the notification. No cache is enabled yet. */
unsigned char __fastcall__ udeks_window_image_complete(unsigned char handle);
unsigned char udeks_window_get_geometry(
    unsigned char handle, unsigned int *x, unsigned char *y,
    unsigned int *width, unsigned char *height);
unsigned char udeks_window_is_dragging(unsigned char handle);
unsigned char udeks_window_is_focused(unsigned char handle);
/* UAPP 0.4: consume one client-area primary click, window-relative pixels.
 * Returns 0 if absent/unsupported. Never consumes console keyboard input. */
struct udeks_window_click { unsigned int x; unsigned char y; };
const struct udeks_window_click * __fastcall__ udeks_window_take_click(unsigned char handle);

#endif
