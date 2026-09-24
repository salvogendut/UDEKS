; SPDX-License-Identifier: GPL-3.0-or-later
;
; Static application adapter used until the task loader owns application polls.

        .setcpu "6502"
        .import _udeks_xclock_initialize
        .import _udeks_xclock_poll
        .export _udeks_xclock_service_descriptor

        .segment "RODATA"
_udeks_xclock_service_descriptor:
        .byte 'U', 'S', 'V', 'C'
        .byte $00, $01
        .byte $0a, $00
        .byte $00, $10
        .addr _udeks_xclock_initialize
        .addr _udeks_xclock_poll
        .addr $0000
descriptor_end:
        .assert descriptor_end - _udeks_xclock_service_descriptor = $10, error, "service descriptor size drift"
