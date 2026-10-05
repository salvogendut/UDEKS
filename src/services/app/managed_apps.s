; SPDX-License-Identifier: GPL-3.0-or-later
; Lifecycle glue for independently scheduled native clients.
        .setcpu "6502"
        .export _udeks_managed_apps_start, _udeks_managed_apps_poll
        .import _udeks_banked_graphics_poll
        .segment "CODE"
_udeks_managed_apps_start:
        lda #0
        tax
        rts
_udeks_managed_apps_poll:
        jsr _udeks_banked_graphics_poll
        lda #0
        tax
        rts
