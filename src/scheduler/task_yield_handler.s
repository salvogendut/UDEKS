; SPDX-License-Identifier: GPL-3.0-or-later
;
; Post-startup lifecycle request handler in the dead boot/probe page. The
; common switch tail has already captured the task CPU/MMU context before
; entering here. Carry set suspends the caller; carry clear resumes a rejected
; request synchronously.

        .setcpu "6502"

        .export _udeks_task_yield_handler
        .import _udeks_task_context_save_current
        .import _udeks_lifecycle_slots_private
        .import _udeks_lifecycle_current_private
        .import _udeks_lifecycle_last_event_private
        .import _udeks_lifecycle_rejected_private
        .import _udeks_bootfs_finish_error

TREQ_BASE               = $f359
TREQ_STATE              = TREQ_BASE+$06
TREQ_OPERATION          = TREQ_BASE+$07
TREQ_DESCRIPTOR         = TREQ_BASE+$09
TREQ_COUNT              = TREQ_BASE+$0a
TREQ_RESULT             = TREQ_BASE+$0b
TREQ_ERROR              = TREQ_BASE+$0c
TREQ_FLAGS              = TREQ_BASE+$0d
TREQ_PAYLOAD             = TREQ_BASE+$0e

TREQ_IDLE               = $00
TREQ_COMPLETE           = $02
ERR_EINVAL              = $16
ERR_ENOSYS              = $26

OP_YIELD                = $0a
OP_EXIT                 = $0b
TASK_SLOT_STRIDE        = $08
TASK_SLOT_STATE         = $01
TASK_SLOT_EXIT          = $04
TASK_STATE_RUNNABLE     = $02
TASK_STATE_RUNNING      = $03
TASK_STATE_ZOMBIE       = $06
LIFECYCLE_YIELD         = $04
LIFECYCLE_EXIT          = $09

        .segment "YIELDHANDLER"

_udeks_task_yield_handler:
        lda TREQ_DESCRIPTOR
        ora TREQ_FLAGS
        bne yield_invalid

        lda TREQ_OPERATION
        cmp #OP_YIELD
        beq request_yield
        cmp #OP_EXIT
        beq request_exit
        lda #ERR_ENOSYS
        jmp _udeks_bootfs_finish_error

request_yield:
        lda TREQ_COUNT
        bne yield_invalid
        jsr current_slot
        bne yield_invalid
        txa
        pha
        jsr _udeks_task_context_save_current
        pla
        tax
        lda #TASK_STATE_RUNNABLE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #LIFECYCLE_YIELD
        sta _udeks_lifecycle_last_event_private
        lda #TREQ_COMPLETE
        sta TREQ_STATE
        lda #$00
        sta _udeks_lifecycle_current_private
        sta TREQ_RESULT
        sta TREQ_ERROR
        sec
        rts

request_exit:
        lda TREQ_COUNT
        cmp #$01
        bne yield_invalid
        jsr current_slot
        bne yield_invalid
        lda TREQ_PAYLOAD
        sta _udeks_lifecycle_slots_private+TASK_SLOT_EXIT,x
        lda #TASK_STATE_ZOMBIE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #LIFECYCLE_EXIT
        sta _udeks_lifecycle_last_event_private
        ; EXIT never publishes a response to the dead caller. Release the
        ; shared record before returning to the kernel poll frame.
        lda #$00
        sta _udeks_lifecycle_current_private
        sta TREQ_STATE
        sta TREQ_RESULT
        sta TREQ_ERROR
        sec
        rts

; Return Z set and X=(current-1)*8 only for a current RUNNING task.
current_slot:
        lda _udeks_lifecycle_current_private
        beq no_current_slot
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_RUNNING
        rts
no_current_slot:
        lda #$01
        rts

yield_invalid:
        inc _udeks_lifecycle_rejected_private
        lda #ERR_EINVAL
        jmp _udeks_bootfs_finish_error

yield_handler_end:
        .assert _udeks_task_yield_handler = $0b00, error, "lifecycle handler moved"
        .assert yield_handler_end <= $0c00, error, "lifecycle handler exceeds boot page"
