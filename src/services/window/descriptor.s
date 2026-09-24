; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .import _udeks_window_manager_start
        .import _udeks_window_manager_poll
        .import _udeks_window_manager_stop
        .export _udeks_window_service_descriptor

        .segment "RODATA"
_udeks_window_service_descriptor:
        .byte 'U', 'S', 'V', 'C'
        .byte $00, $01
        .byte $09, $00
        .byte $01, $10
        .addr _udeks_window_manager_start
        .addr _udeks_window_manager_poll
        .addr _udeks_window_manager_stop
descriptor_end:
        .assert descriptor_end - _udeks_window_service_descriptor = $10, error, "service descriptor size drift"
