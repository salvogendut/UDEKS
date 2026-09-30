; SPDX-License-Identifier: GPL-3.0-or-later
;
; Transitional init service. It is the sole registry-visible owner of the
; root user session. It polls the persistent bank-1 /bin/ush task while also
; delegating to the resident bootstrap shell during the extraction transition.

        .setcpu "6502"
        .import _udeks_shell_start
        .import _udeks_shell_poll
        .export _udeks_init_service_descriptor
        .export _udeks_shell_read_line
_udeks_shell_read_line = $c90f

TASK_BANK_POLL          = $ff13
PERSISTENT_LOAD         = $f910
LIFECYCLE_BOOTSTRAP     = $1c1e
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
        jsr LIFECYCLE_BOOTSTRAP
init_shell_fallback:
        jmp _udeks_shell_start
        ; Preserve the frozen resident/VIC-shadow boundary while replacing
        ; the former reset+first-poll calls with the scheduler bootstrap gate.
        .res $03, $ea
        ; Storage 0.2's explicit loader-result handling saves nine resident
        ; CODE bytes. Preserve the qualified shadow and delivery addresses.
        .res 9, $ea

init_poll:
        jsr $c903                       ; wake SLEEP/input event requests
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
