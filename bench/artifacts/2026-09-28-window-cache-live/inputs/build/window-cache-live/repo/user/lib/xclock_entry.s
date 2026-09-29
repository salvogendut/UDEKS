; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .segment "STARTUP"
        .import _udeks_xclock_initialize
        .import _udeks_xclock_start
        .import _udeks_xclock_poll
        .import _udeks_xclock_stop
        .import _udeks_xclock_is_running
        .import _udeks_xclock_is_focused

_udeks_xclock_entry:
        jmp _udeks_xclock_initialize
        jmp _udeks_xclock_start
        jmp _udeks_xclock_poll
        jmp _udeks_xclock_stop
        jmp _udeks_xclock_is_running
        jmp _udeks_xclock_is_focused
        .assert _udeks_xclock_entry = $0200, error, "xclock entry moved"
