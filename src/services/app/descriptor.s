; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .import _udeks_managed_apps_start
        .import _udeks_managed_apps_poll
        .export _udeks_managed_apps_service_descriptor

        .segment "RODATA"
_udeks_managed_apps_service_descriptor:
        .byte 'U', 'S', 'V', 'C'
        .byte $00, $01
        .byte $0a, $00
        .byte $00, $10
        .addr _udeks_managed_apps_start
        .addr _udeks_managed_apps_poll
        .addr $0000
descriptor_end:
        .assert descriptor_end - _udeks_managed_apps_service_descriptor = $10, error, "managed app descriptor size drift"
