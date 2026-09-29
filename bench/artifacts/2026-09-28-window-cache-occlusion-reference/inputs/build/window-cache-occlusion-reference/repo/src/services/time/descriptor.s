; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .import _udeks_time_start
        .import _udeks_time_poll
        .export _udeks_time_service_descriptor

        .segment "RODATA"
_udeks_time_service_descriptor:
        .byte 'U', 'S', 'V', 'C'
        .byte $00, $01
        .byte $04, $01
        .byte $01, $10
        .addr _udeks_time_start
        .addr _udeks_time_poll
        .addr $0000
descriptor_end:
        .assert descriptor_end - _udeks_time_service_descriptor = $10, error, "service descriptor size drift"
