/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_POINTER_H
#define UDEKS_POINTER_H

#define UDEKS_POINTER_STATUS_BASE       0xF1D0u
#define UDEKS_POINTER_STATUS_SIZE       32u

#define UDEKS_POINTER_STARTING          1u
#define UDEKS_POINTER_READY             2u
#define UDEKS_POINTER_ERROR             0x80u

#define UDEKS_POINTER_OK                0u

#define UDEKS_POINTER_FLAG_MOUSE1       0x01u
#define UDEKS_POINTER_FLAG_JOYSTICK2    0x02u
#define UDEKS_POINTER_FLAG_1351         0x04u
#define UDEKS_POINTER_FLAG_FRAME_POLL   0x08u

#define UDEKS_POINTER_SOURCE_MOUSE      0x01u
#define UDEKS_POINTER_SOURCE_JOYSTICK   0x02u

#define UDEKS_POINTER_X_MIN             18u
#define UDEKS_POINTER_X_MAX             326u
#define UDEKS_POINTER_Y_MIN             45u
#define UDEKS_POINTER_Y_MAX             234u
#define UDEKS_POINTER_X_INITIAL         172u
#define UDEKS_POINTER_Y_INITIAL         140u

unsigned char udeks_pointer_start(void);
unsigned char udeks_pointer_poll(void);
unsigned char udeks_pointer_keyboard_allowed(void);
unsigned int udeks_pointer_x(void);
unsigned char udeks_pointer_y(void);
unsigned char udeks_pointer_buttons(void);

#endif
