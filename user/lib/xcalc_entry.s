; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .segment "STARTUP"
        .import __BSS_RUN__, __BSS_SIZE__
        .assert * = $0200, lderror, "xcalc entry moved"
        .assert __BSS_SIZE__ <= $22, lderror, "xcalc BSS exceeds UDEX reservation"
        .assert __BSS_RUN__+$22 <= $1200, lderror, "xcalc exceeds managed slot"
        .import _udeks_xcalc_initialize, _udeks_xcalc_start
        .import _udeks_xcalc_poll, _udeks_xcalc_stop
        .import _udeks_xcalc_is_running, _udeks_xcalc_is_focused
        jmp _udeks_xcalc_initialize
        jmp _udeks_xcalc_start
        jmp _udeks_xcalc_poll
        jmp _udeks_xcalc_stop
        jmp _udeks_xcalc_is_running
        jmp _udeks_xcalc_is_focused
