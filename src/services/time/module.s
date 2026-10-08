; SPDX-License-Identifier: GPL-3.0-or-later
; Standalone time module: no imports from a particular kernel link.
        .setcpu "6502"
        .import _udeks_time_start, _udeks_time_poll, _udeks_time_stop
        .import __BSS_SIZE__, __BSS_RUN__
        .export _udeks_time_sync_ti
        .importzp tmp1

        .segment "HEADER"
module:
        .byte "USVM", 0, 1, 4, 1
        .word module, __BSS_RUN__-module, __BSS_SIZE__, 0
        .word 0                       ; patched checksum of emitted image
        .word 1                       ; module revision (not ABI version)
        .word clock_set_runtime
        .res 10, 0                    ; reserved; must stay zero
        .byte "USVC", 0, 1, 4, 1, 0, 16
        .word _udeks_time_start, _udeks_time_poll, _udeks_time_stop
        .assert *-module = 48, error, "service image header size changed"

        .segment "CODE"
        .include "clock_set.inc"
