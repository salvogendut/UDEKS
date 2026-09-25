; SPDX-License-Identifier: GPL-3.0-or-later
;
; Transitional init service. It is the sole registry-visible owner of the
; root user session and delegates to the resident bootstrap shell until
; /bin/ush can run through the task and stream ABIs.

        .setcpu "6502"
        .import _udeks_shell_start
        .import _udeks_shell_poll
        .export _udeks_init_service_descriptor

        .segment "CODE"
init_start:
        jmp _udeks_shell_start

init_poll:
        jmp _udeks_shell_poll

        .segment "RODATA"
_udeks_init_service_descriptor:
        .byte 'U', 'S', 'V', 'C'
        .byte $00, $01
        .byte $0b, $00
        .byte $01, $10
        .addr init_start
        .addr init_poll
        .addr $0000
descriptor_end:
        .assert descriptor_end - _udeks_init_service_descriptor = $10, error, "service descriptor size drift"
