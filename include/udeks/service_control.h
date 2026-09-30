/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_SERVICE_CONTROL_H
#define UDEKS_SERVICE_CONTROL_H
#include "udeks/task_request.h"
#define UDEKS_CONTROL_DESKTOP 1u
#define UDEKS_CONTROL_CLOCK   2u
#define UDEKS_CONTROL_WAVE    3u
#define UDEKS_CONTROL_ENGINE  4u
#define UDEKS_CONTROL_START   0u
#define UDEKS_CONTROL_STOP    1u
#define UDEKS_CONTROL_TEST    2u
#define UDEKS_CONTROL_BACKGROUND 1u
#define UDEKS_CONTROL_COUNT   3u
/* Serialized root-session reply. EXEC copies its input before reusing this
 * mailbox. UTRQ calls do not overwrite it. Consumer clears READY before I/O.
 * [ready, target, action, background, service result]; READY published last. */
#define UDEKS_CONTROL_REPLY_BASE UDEKS_TASK_COMMAND_BASE
#define UDEKS_CONTROL_REPLY_READY 0xA5u
#define UDEKS_CONTROL_INTERRUPTED 130u
/* Managed-app completion results; 1/2 retain the app's existing meanings.
 * NOT_FOUND also covers an unmounted command disk. Not POSIX errno values. */
#define UDEKS_CONTROL_NOT_READY       1u
#define UDEKS_CONTROL_ALREADY_RUNNING 2u
#define UDEKS_CONTROL_NOT_FOUND       3u
#define UDEKS_CONTROL_SLOT_BUSY       4u
#define UDEKS_CONTROL_BAD_PROGRAM     5u
#define UDEKS_CONTROL_DISK_ERROR      6u

#ifdef UDEKS_CONTROL_VALIDATE
static unsigned char udeks_control_valid(unsigned char target,
    unsigned char action, unsigned char background)
{
    if (target < UDEKS_CONTROL_DESKTOP || target > UDEKS_CONTROL_ENGINE ||
        background > 1u) return 0;
    if (target == UDEKS_CONTROL_ENGINE)
        return action == UDEKS_CONTROL_TEST && !background;
    if (action > UDEKS_CONTROL_STOP) return 0;
    return !background || (target != UDEKS_CONTROL_DESKTOP &&
                           action == UDEKS_CONTROL_START);
}
#endif
#endif
