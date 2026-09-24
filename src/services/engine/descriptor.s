; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .import _udeks_z80_worker_start
        .export _udeks_z80_worker_service_descriptor

        .segment "RODATA"
_udeks_z80_worker_service_descriptor:
        .byte 'U', 'S', 'V', 'C'
        .byte $00, $01
        .byte $08, $00
        .byte $01, $10
        .addr _udeks_z80_worker_start
        .addr $0000
        .addr $0000
descriptor_end:
        .assert descriptor_end - _udeks_z80_worker_service_descriptor = $10, error, "service descriptor size drift"
