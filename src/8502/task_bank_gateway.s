; SPDX-License-Identifier: GPL-3.0-or-later
;
; Common-RAM 8502 bank-1 cooperative task gate. This is linked with the
; resident image so its fixed ABI and placement are checked together, but its
; bytes are staged and installed separately by the native boot path.

        .setcpu "6502"
        .segment "TASKGATE"

        .export _udeks_task_bank_gate
        .export _udeks_task_bank_reset_gate
        .export _udeks_task_bank_poll_gate

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_FLAT     = $ff04
TASK_ENTRY              = $9000
TASK_USER_ZP            = $8fe0
CC65_ZP_FIRST           = $02
CC65_ZP_SIZE            = $1e
CC65_SP_INDEX           = $04
TASK_STACK_TOP          = $eff0

TASK_STATE_EMPTY        = $00
TASK_STATE_READY        = $01
TASK_STATE_RUNNING      = $02
TASK_NOT_READY          = $01

_udeks_task_bank_gate:
        .byte 'U', 'T', 'G', '1'
        .byte $00, $01
task_state:
        .byte TASK_STATE_EMPTY
task_last_result:
        .byte $00
task_polls_low:
        .byte $00
task_polls_high:
        .byte $00
        .byte $00

        .assert * = $ff10, error, "bank-task reset vector moved"
_udeks_task_bank_reset_gate:
        jmp task_reset
_udeks_task_bank_poll_gate:
        jmp task_poll
        .res $0a, $00

task_reset:
        php
        sei
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        ldx #CC65_ZP_SIZE-1
        lda #$00
task_reset_zp:
        sta TASK_USER_ZP,x
        dex
        bpl task_reset_zp
        lda #<TASK_STACK_TOP
        sta TASK_USER_ZP+CC65_SP_INDEX
        lda #>TASK_STACK_TOP
        sta TASK_USER_ZP+CC65_SP_INDEX+1
        lda #$00
        sta MMU_LCR_KERNEL_IO
        lda #TASK_STATE_READY
        sta task_state
        lda #$00
        sta task_last_result
        sta task_polls_low
        sta task_polls_high
        plp
        rts

task_poll:
        lda task_state
        cmp #TASK_STATE_READY
        beq task_enter
        lda #TASK_NOT_READY
        ldx #$00
        rts

task_enter:
        php
        sei
        lda #TASK_STATE_RUNNING
        sta task_state
        ldx #CC65_ZP_SIZE-1
task_save_kernel_zp:
        lda CC65_ZP_FIRST,x
        sta task_kernel_zp,x
        dex
        bpl task_save_kernel_zp

        lda #$00
        sta MMU_LCR_WORKER_FLAT
        ldx #CC65_ZP_SIZE-1
task_restore_user_zp:
        lda TASK_USER_ZP,x
        sta CC65_ZP_FIRST,x
        dex
        bpl task_restore_user_zp
        jsr TASK_ENTRY
        pha
        txa
        pha

        ldx #CC65_ZP_SIZE-1
task_save_user_zp:
        lda CC65_ZP_FIRST,x
        sta TASK_USER_ZP,x
        dex
        bpl task_save_user_zp

        lda #$00
        sta MMU_LCR_KERNEL_IO
        ldx #CC65_ZP_SIZE-1
task_restore_kernel_zp:
        lda task_kernel_zp,x
        sta CC65_ZP_FIRST,x
        dex
        bpl task_restore_kernel_zp

        pla
        tax
        pla
        sta task_last_result
        pha

        inc task_polls_low
        bne task_poll_counted
        inc task_polls_high
task_poll_counted:
        lda #TASK_STATE_READY
        sta task_state
        pla
        plp
        rts

task_gate_end:
        .assert task_gate_end <= $ffd0, error, "bank-task gate overlaps CPU handoff"

        .segment "BSS"
task_kernel_zp:         .res CC65_ZP_SIZE
