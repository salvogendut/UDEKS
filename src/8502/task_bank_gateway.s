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
        .export _udeks_task_bank_request_gate

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_FLAT     = $ff04
TASK_ENTRY              = $9000
TASK_CONTEXT            = $e2e2
TASK_REQUEST_DISPATCH   = $cf30
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
        .byte $00, $02
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
_udeks_task_bank_request_gate:
        jmp task_request
        .res $07, $00

task_reset:
        php
        sei
        sta MMU_LCR_WORKER_FLAT
        ldx #CC65_ZP_SIZE-1
        lda #$00
task_reset_zp:
        sta TASK_CONTEXT,x
        dex
        bpl task_reset_zp
        lda #<TASK_STACK_TOP
        sta TASK_CONTEXT+CC65_SP_INDEX
        lda #>TASK_STACK_TOP
        sta TASK_CONTEXT+CC65_SP_INDEX+1
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
        jsr task_save_zp
        sta MMU_LCR_WORKER_FLAT
        jsr task_restore_zp
        jsr TASK_ENTRY
        pha
        txa
        pha
        jsr task_save_zp
        sta MMU_LCR_KERNEL_IO
        jsr task_restore_zp
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

        ; Synchronous bank-1 request. The caller has filled the common request
        ; record. Swap to the resident runtime, dispatch it at $CF30, then
        ; restore the task runtime before returning through the same C stack.
task_request:
        php
        sei
        jsr task_save_zp
        sta MMU_LCR_KERNEL_IO
        jsr task_restore_zp
        jsr TASK_REQUEST_DISPATCH
        pha
        txa
        pha
        jsr task_save_zp
        sta MMU_LCR_WORKER_FLAT
        jsr task_restore_zp
        pla
        tax
        pla
        plp
        rts

        ; Both physical banks reserve $E2E2-$E2FF for their selected cc65
        ; zero-page image. The active MMU map chooses the context implicitly.
task_save_zp:
        ldx #CC65_ZP_SIZE-1
task_save_zp_byte:
        lda CC65_ZP_FIRST,x
        sta TASK_CONTEXT,x
        dex
        bpl task_save_zp_byte
        rts

task_restore_zp:
        ldx #CC65_ZP_SIZE-1
task_restore_zp_byte:
        lda TASK_CONTEXT,x
        sta CC65_ZP_FIRST,x
        dex
        bpl task_restore_zp_byte
        rts

task_gate_end:
        .assert task_gate_end <= $ffd0, error, "bank-task gate overlaps CPU handoff"
