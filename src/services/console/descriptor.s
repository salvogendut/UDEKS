; SPDX-License-Identifier: GPL-3.0-or-later
;
; Compiler-neutral service descriptor. All vectors are little-endian absolute
; addresses resolved by ld65; zero denotes an unsupported lifecycle operation.

        .setcpu "6502"
        .import _udeks_console_start
        .export _udeks_console_service_descriptor

        .segment "RODATA"
_udeks_console_service_descriptor:
.ifdef UDEKS_FAULT_SERVICE_MAGIC
        .byte 'X', 'S', 'V', 'C'
.else
        .byte 'U', 'S', 'V', 'C'
.endif
        .byte $00, $01
        .byte $01, $00
        .byte $03, $10
        .addr _udeks_console_start
        .addr $0000
        .addr $0000
descriptor_end:
        .assert descriptor_end - _udeks_console_service_descriptor = $10, error, "service descriptor size drift"
