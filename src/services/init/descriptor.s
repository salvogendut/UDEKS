; SPDX-License-Identifier: GPL-3.0-or-later
;
; Transitional init service. It is the sole registry-visible owner of the
; root user session. It polls the persistent bank-1 /bin/ush task while also
; delegating to the resident bootstrap shell during the extraction transition.

        .setcpu "6502"
        .import _udeks_shell_start
        .import _udeks_shell_poll
        .export _udeks_init_service_descriptor

TASK_BANK_RESET         = $ff10
TASK_BANK_POLL          = $ff13
PERSISTENT_LOAD         = $f910
TASK_STATE              = $f285
USH_STATE               = $f3d9

        .segment "CODE"
init_start:
        lda #$00
        sta TASK_STATE
        sta USH_STATE
        lda #<ush_name
        ldx #>ush_name
        jsr PERSISTENT_LOAD
        bne init_shell_fallback
        jsr TASK_BANK_RESET
        jsr TASK_BANK_POLL
init_shell_fallback:
        jmp _udeks_shell_start

init_poll:
        jsr TASK_BANK_POLL
        jmp _udeks_shell_poll

ush_name:
        .byte "ush", $00

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
