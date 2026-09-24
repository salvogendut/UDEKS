; SPDX-License-Identifier: GPL-3.0-or-later
;
; Static application adapter used until the task loader owns application polls.

        .setcpu "6502"
        .import _udeks_xwave_initialize
        .import _udeks_xwave_poll
        .export _udeks_xwave_service_descriptor

        .segment "RODATA"
_udeks_xwave_service_descriptor:
        .byte 'U', 'S', 'V', 'C'
        .byte $00, $01
        .byte $0a, $01
        .byte $00, $10
        .addr _udeks_xwave_initialize
        .addr _udeks_xwave_poll
        .addr $0000
descriptor_end:
        .assert descriptor_end - _udeks_xwave_service_descriptor = $10, error, "service descriptor size drift"
