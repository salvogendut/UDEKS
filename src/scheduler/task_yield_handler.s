; SPDX-License-Identifier: GPL-3.0-or-later
;
; Post-startup lifecycle request handler in the permanent scheduler tail. The
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
        .import _udeks_task_wait_state_private
        .import _udeks_task_wait_operation_private
        .import _udeks_task_wait_sequence_private
        .import _udeks_task_wait_descriptor_private
        .import _udeks_task_wait_count_private
        .import _udeks_task_wait_flags_private
        .import _udeks_task_wait_selector_private
        .import _udeks_task_wait_selector_high_private
        .import _udeks_task_wait_child_private
        .import _udeks_task_wait_status_private
        .import _udeks_bootfs_finish_error
        .import _udeks_bootfs_finish_ok

TREQ_BASE               = $f359
TREQ_STATE              = TREQ_BASE+$06
TREQ_OPERATION          = TREQ_BASE+$07
TREQ_SEQUENCE           = TREQ_BASE+$08
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
OP_WAITPID              = $0c
WAITPID_NOHANG          = $01
TASK_SLOT_STRIDE        = $08
TASK_SLOT_PARENT        = $00
TASK_SLOT_STATE         = $01
TASK_SLOT_WAIT          = $02
TASK_SLOT_EXIT          = $04
TASK_SLOT_RESUME        = $06
TASK_SLOT_TABLE_SIZE    = $40
TASK_STATE_FREE         = $00
TASK_STATE_RUNNABLE     = $02
TASK_STATE_RUNNING      = $03
TASK_STATE_WAITING      = $04
TASK_STATE_ZOMBIE       = $06
LIFECYCLE_YIELD         = $04
LIFECYCLE_BLOCK         = $05
LIFECYCLE_EXIT          = $09
LIFECYCLE_REAP          = $0a
WAIT_CHILD              = $01
WAIT_BLOCKED            = $01
WAIT_READY              = $02
ERR_ECHILD              = $0a

        .segment "YIELDHANDLER"

_udeks_task_yield_handler:
        lda TREQ_DESCRIPTOR
        beq :+
        jmp yield_invalid
:

        lda TREQ_OPERATION
        cmp #OP_YIELD
        beq request_yield
        cmp #OP_EXIT
        bne :+
        jmp request_exit
:
        cmp #OP_WAITPID
        bne :+
        jmp request_waitpid
:
        lda #ERR_ENOSYS
        jmp _udeks_bootfs_finish_error

request_yield:
        lda TREQ_COUNT
        ora TREQ_FLAGS
        beq :+
        jmp yield_invalid
:
        jsr current_slot
        beq :+
        jmp yield_invalid
:
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

request_waitpid:
        lda TREQ_COUNT
        cmp #$02
        beq :+
        jmp yield_invalid
:
        lda TREQ_FLAGS
        and #$fe
        beq :+
        jmp yield_invalid
:
        jsr current_slot
        beq :+
        jmp yield_invalid
:
        lda TREQ_PAYLOAD+1
        beq :+
        jmp wait_no_child
:
        lda TREQ_PAYLOAD
        beq wait_any_child
        cmp #$09
        bcc :+
        jmp wait_no_child
:
        cmp _udeks_lifecycle_current_private
        bne :+
        jmp wait_no_child
:
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        bne :+
        jmp wait_no_child
:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_PARENT,x
        cmp _udeks_lifecycle_current_private
        beq :+
        jmp wait_no_child
:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_ZOMBIE
        bne wait_live_child
        jmp wait_reap

wait_any_child:
        ldx #$00
        ldy #$00
wait_scan:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_PARENT,x
        cmp _udeks_lifecycle_current_private
        bne wait_next
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        beq wait_next
        cmp #TASK_STATE_ZOMBIE
        bne :+
        jmp wait_reap
:
        ldy #$01
wait_next:
        txa
        clc
        adc #TASK_SLOT_STRIDE
        tax
        cmp #TASK_SLOT_TABLE_SIZE
        bne wait_scan
        tya
        bne wait_live_child
        jmp wait_no_child

wait_live_child:
        lda TREQ_FLAGS
        and #WAITPID_NOHANG
        beq wait_blocking
        lda #$00
        jmp _udeks_bootfs_finish_ok

wait_blocking:
        ; Snapshot the fields required to publish this task's eventual
        ; response, then release the shared request record before sleeping.
        lda _udeks_lifecycle_current_private
        sec
        sbc #$01
        tay
        lda TREQ_OPERATION
        sta _udeks_task_wait_operation_private,y
        lda TREQ_SEQUENCE
        sta _udeks_task_wait_sequence_private,y
        lda TREQ_DESCRIPTOR
        sta _udeks_task_wait_descriptor_private,y
        lda TREQ_COUNT
        sta _udeks_task_wait_count_private,y
        lda TREQ_FLAGS
        sta _udeks_task_wait_flags_private,y
        lda TREQ_PAYLOAD
        sta _udeks_task_wait_selector_private,y
        lda TREQ_PAYLOAD+1
        sta _udeks_task_wait_selector_high_private,y
        lda #WAIT_BLOCKED
        sta _udeks_task_wait_state_private,y
        jsr _udeks_task_context_save_current

        lda _udeks_lifecycle_current_private
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda #WAIT_CHILD
        sta _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        lda #TASK_STATE_WAITING
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #LIFECYCLE_BLOCK
        sta _udeks_lifecycle_last_event_private
        lda #$00
        sta _udeks_lifecycle_current_private
        sta TREQ_STATE
        sta TREQ_RESULT
        sta TREQ_ERROR
        sec
        rts

wait_reap:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_EXIT,x
        sta TREQ_PAYLOAD+2
        txa
        lsr a
        lsr a
        lsr a
        clc
        adc #$01
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_PAYLOAD+1
        sta TREQ_PAYLOAD+3
        ldy #TASK_SLOT_STRIDE
wait_clear_slot:
        sta _udeks_lifecycle_slots_private,x
        inx
        dey
        bne wait_clear_slot
        lda #LIFECYCLE_REAP
        sta _udeks_lifecycle_last_event_private
        lda #$01
        jmp _udeks_bootfs_finish_ok

wait_no_child:
        lda #ERR_ECHILD
        jmp _udeks_bootfs_finish_error

request_exit:
        lda TREQ_FLAGS
        beq :+
        jmp yield_invalid
:
        lda TREQ_COUNT
        cmp #$01
        beq :+
        jmp yield_invalid
:
        jsr current_slot
        beq :+
        jmp yield_invalid
:
        lda TREQ_PAYLOAD
        sta _udeks_lifecycle_slots_private+TASK_SLOT_EXIT,x
        lda #TASK_STATE_ZOMBIE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #LIFECYCLE_EXIT
        sta _udeks_lifecycle_last_event_private
        ; A blocked parent owns a private WAITPID snapshot. If this child
        ; matches it, move the response there, reap the child, and make the
        ; parent runnable. The shared request still belongs to this EXIT call.
        lda _udeks_lifecycle_slots_private+TASK_SLOT_PARENT,x
        beq exit_release
        sec
        sbc #$01
        tay
        lda _udeks_task_wait_state_private,y
        cmp #WAIT_BLOCKED
        bne exit_release
        lda _udeks_task_wait_selector_private,y
        beq exit_parent_slot
        cmp _udeks_lifecycle_current_private
        bne exit_release
exit_parent_slot:
        tya
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_WAITING
        bne exit_release
        lda _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        cmp #WAIT_CHILD
        bne exit_release

        lda _udeks_lifecycle_current_private
        sta _udeks_task_wait_child_private,y
        lda TREQ_PAYLOAD
        sta _udeks_task_wait_status_private,y
        lda #WAIT_READY
        sta _udeks_task_wait_state_private,y
        lda #$00
        sta _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        sta _udeks_lifecycle_slots_private+TASK_SLOT_RESUME,x
        lda #TASK_STATE_RUNNABLE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x

        lda _udeks_lifecycle_current_private
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda #$00
        ldy #TASK_SLOT_STRIDE
exit_clear_child:
        sta _udeks_lifecycle_slots_private,x
        inx
        dey
        bne exit_clear_child
        lda #LIFECYCLE_REAP
        sta _udeks_lifecycle_last_event_private
exit_release:
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
        .assert _udeks_task_yield_handler = $cb00, error, "lifecycle handler moved"
        .assert yield_handler_end <= $cdbd, error, "lifecycle handler reaches context binding"
