; SPDX-License-Identifier: GPL-3.0-or-later
;
; Persistent UDEX entry: every call is one bounded cooperative poll. A tail
; jump lets the C function's RTS return directly through the common task gate.

        .setcpu "6502"
        .segment "STARTUP"

        .export _udeks_task_poll_entry
        .import _udeks_ush_poll

_udeks_task_poll_entry:
        jmp _udeks_ush_poll
