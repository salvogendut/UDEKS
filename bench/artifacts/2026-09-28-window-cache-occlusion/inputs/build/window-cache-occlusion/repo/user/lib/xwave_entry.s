; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .segment "STARTUP"
        .import _udeks_xwave_initialize
        .import _udeks_xwave_start
        .import _udeks_xwave_poll
        .import _udeks_xwave_stop
        .import _udeks_xwave_is_running
        .import _udeks_xwave_is_focused

_udeks_xwave_entry:
        jmp _udeks_xwave_initialize
        jmp _udeks_xwave_start
        jmp _udeks_xwave_poll
        jmp _udeks_xwave_stop
        jmp _udeks_xwave_is_running
        jmp _udeks_xwave_is_focused
        .assert _udeks_xwave_entry = $1200, error, "xwave entry moved"
