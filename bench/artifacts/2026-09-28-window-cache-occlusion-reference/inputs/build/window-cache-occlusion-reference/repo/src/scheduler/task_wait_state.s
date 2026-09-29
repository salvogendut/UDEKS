; SPDX-License-Identifier: GPL-3.0-or-later
;
; Per-task ownership for lifecycle requests that outlive the shared $F359
; record. The request handler snapshots blocking WAITPID/SLEEP/POLL here, EXIT
; turns a matching child wait into a ready response, CANCEL discards a dead
; task's snapshot, and context selection publishes before restoring a task.

        .setcpu "6502"
        .macpack longbranch

        .export _udeks_task_wait_reset
        .export _udeks_task_wait_publish_current
        .export _udeks_task_wait_state_private
        .export _udeks_task_wait_operation_private
        .export _udeks_task_wait_sequence_private
        .export _udeks_task_wait_descriptor_private
        .export _udeks_task_wait_count_private
        .export _udeks_task_wait_flags_private
        .export _udeks_task_wait_selector_private
        .export _udeks_task_wait_selector_high_private
        .export _udeks_task_wait_child_private
        .export _udeks_task_wait_status_private
        .export _udeks_task_sleep_poll
        .export _udeks_task_tick_advance
        .export _udeks_task_cancel_request
        .export _udeks_task_poll_request
        .export _udeks_task_console_get_line
        .export _udeks_monotonic_ticks_low
        .export _udeks_monotonic_ticks_high
        .import _udeks_lifecycle_current_private
        .import _udeks_lifecycle_last_event_private
        .import _udeks_lifecycle_rejected_private
        .import _udeks_lifecycle_slots_private
        .import _udeks_bootfs_finish_error
        .import _udeks_bootfs_finish_ok
        .import _udeks_line_editor_submitted_ready_value
        .import _udeks_line_editor_get_line
        .import incsp2

TASK_COUNT              = $08
WAIT_READY              = $02
OP_SLEEP                = $0d
OP_CANCEL               = $0e
OP_POLL                 = $10
WAIT_BLOCKED            = $01
WAIT_TIMER              = $03
WAIT_INPUT              = $02
TASK_SLOT_STRIDE        = $08
TASK_SLOT_PARENT        = $00
TASK_SLOT_STATE         = $01
TASK_SLOT_WAIT          = $02
TASK_SLOT_EXIT          = $04
TASK_SLOT_RESUME        = $06
TASK_STATE_FREE         = $00
TASK_STATE_RUNNABLE     = $02
TASK_STATE_RUNNING      = $03
TASK_STATE_WAITING      = $04
TASK_STATE_STOPPED      = $05
TASK_STATE_ZOMBIE       = $06
LIFECYCLE_CANCEL        = $0b
ERR_ESRCH               = $03
ERR_EINVAL              = $16

TREQ_BASE               = $f359
TREQ_MINOR              = TREQ_BASE+$05
TREQ_STATE              = TREQ_BASE+$06
TREQ_OPERATION          = TREQ_BASE+$07
TREQ_SEQUENCE           = TREQ_BASE+$08
TREQ_DESCRIPTOR         = TREQ_BASE+$09
TREQ_COUNT              = TREQ_BASE+$0a
TREQ_RESULT             = TREQ_BASE+$0b
TREQ_ERROR              = TREQ_BASE+$0c
TREQ_FLAGS              = TREQ_BASE+$0d
TREQ_PAYLOAD            = TREQ_BASE+$0e

TREQ_COMPLETE           = $02
CAPABILITY_VIDEO        = $f0c7

        .segment "CODE"

_udeks_task_wait_reset:
        ldx #TASK_COUNT-1
        lda #$00
clear_wait_state:
        sta _udeks_task_wait_state_private,x
        sta _udeks_task_wait_operation_private,x
        sta _udeks_task_wait_sequence_private,x
        sta _udeks_task_wait_descriptor_private,x
        sta _udeks_task_wait_count_private,x
        sta _udeks_task_wait_flags_private,x
        sta _udeks_task_wait_selector_private,x
        sta _udeks_task_wait_selector_high_private,x
        sta _udeks_task_wait_child_private,x
        sta _udeks_task_wait_status_private,x
        dex
        bpl clear_wait_state
        rts

; Preserve the resident foreground/EXEC poll path but prohibit a second
; reader while native ush owns stdin. A remains the legacy capacity argument
; on fallback; native ownership returns EMPTY and pops its pointer argument.
_udeks_task_console_get_line:
        ldx $f3d9
        cpx #$a5
        beq native_console_owner
        jmp _udeks_line_editor_get_line
native_console_owner:
        lda #$01
        ldx #$00
        jmp incsp2

_udeks_task_wait_publish_current:
        lda _udeks_lifecycle_current_private
        jeq publish_done
        tax
        dex
        lda _udeks_task_wait_state_private,x
        cmp #WAIT_READY
        jne publish_done

        lda _udeks_task_wait_operation_private,x
        sta TREQ_OPERATION
        lda _udeks_task_wait_sequence_private,x
        sta TREQ_SEQUENCE
        lda _udeks_task_wait_descriptor_private,x
        sta TREQ_DESCRIPTOR
        lda _udeks_task_wait_count_private,x
        sta TREQ_COUNT
        lda #$00
        sta TREQ_ERROR
        lda _udeks_task_wait_flags_private,x
        sta TREQ_FLAGS
        lda _udeks_task_wait_operation_private,x
        cmp #OP_SLEEP
        beq publish_sleep
        cmp #OP_POLL
        beq publish_poll
        lda #$01
        sta TREQ_RESULT
        lda _udeks_task_wait_child_private,x
        sta TREQ_PAYLOAD
        lda _udeks_task_wait_selector_high_private,x
        sta TREQ_PAYLOAD+1
        lda _udeks_task_wait_status_private,x
        sta TREQ_PAYLOAD+2
        lda #$00
        sta TREQ_PAYLOAD+3
        jmp publish_commit
publish_poll:
        ; POLL's child/status bytes retain the requested timeout; its flags
        ; byte privately holds the ready result. Public request flags are 0.
        lda _udeks_task_wait_flags_private,x
        sta TREQ_RESULT
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_FLAGS
        sta TREQ_PAYLOAD+1
        lda _udeks_task_wait_child_private,x
        sta TREQ_PAYLOAD+2
        lda _udeks_task_wait_status_private,x
        sta TREQ_PAYLOAD+3
        lda #$00
        jmp publish_commit
publish_sleep:
        lda #$00
        sta TREQ_RESULT
        sta TREQ_PAYLOAD
        sta TREQ_PAYLOAD+1
        sta TREQ_PAYLOAD+2
        sta TREQ_PAYLOAD+3
publish_commit:
        sta _udeks_task_wait_state_private,x
        ; State is the publication commit byte and must be written last.
        lda #TREQ_COMPLETE
        sta TREQ_STATE
publish_done:
        rts

; ABI 0.4: a non-consuming readiness wait on stdin. Reuse the private
; snapshot arrays and the qualified fixed helper veneers; allocate no BSS.
_udeks_task_poll_request:
        lda TREQ_MINOR
        cmp #$04
        jne poll_unsupported
        lda _udeks_lifecycle_current_private
        jeq poll_missing
        cmp #TASK_COUNT+1
        jcs poll_missing
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_RUNNING
        jne poll_invalid
        lda TREQ_DESCRIPTOR
        jne poll_bad_descriptor
        lda TREQ_FLAGS
        jne poll_invalid
        lda TREQ_COUNT
        cmp #$04
        jne poll_invalid
        lda TREQ_PAYLOAD
        cmp #$01
        jne poll_invalid
        lda TREQ_PAYLOAD+1
        jne poll_invalid
        lda TREQ_PAYLOAD+3
        cmp #$ff
        bne poll_finite
        lda TREQ_PAYLOAD+2
        cmp #$ff
        beq poll_valid
        bne poll_invalid
poll_finite:
        cmp #$02
        bcc poll_valid
        bne poll_invalid
        lda TREQ_PAYLOAD+2
        cmp #$59
        bcs poll_invalid
poll_valid:
        lda _udeks_line_editor_submitted_ready_value
        bne poll_ready
        lda TREQ_PAYLOAD+2
        ora TREQ_PAYLOAD+3
        beq poll_empty
        jsr $c909                       ; snapshot; returns Y=current-1
        lda TREQ_PAYLOAD+2
        sta _udeks_task_wait_child_private,y
        lda TREQ_PAYLOAD+3
        sta _udeks_task_wait_status_private,y
        cmp #$ff
        beq poll_block                  ; infinite wait has no deadline
        clc
        lda _udeks_monotonic_ticks_low
        adc TREQ_PAYLOAD+2
        sta _udeks_task_wait_selector_private,y
        lda _udeks_monotonic_ticks_high
        adc TREQ_PAYLOAD+3
        sta _udeks_task_wait_selector_high_private,y
poll_block:
        lda #WAIT_INPUT
        jmp $c90c                       ; save context and suspend
poll_ready:
        lda #$01
        bne poll_complete
poll_empty:
        lda #$00
poll_complete:
        sta TREQ_PAYLOAD
        jmp _udeks_bootfs_finish_ok
poll_unsupported:
        lda #$26                       ; ENOSYS
        bne poll_error
poll_missing:
        lda #ERR_ESRCH
        bne poll_error
poll_bad_descriptor:
        lda #$09                       ; EBADF
        bne poll_error
poll_invalid:
        lda #ERR_EINVAL
poll_error:
        jmp _udeks_bootfs_finish_error

; Validate and terminate one live child without ever dispatching it again.
; All rejection checks precede mutation. A blocked child's private request is
; cleared so cancellation cannot later publish a stale response.
_udeks_task_cancel_request:
        lda TREQ_FLAGS
        beq :+
        jmp cancel_invalid
:
        lda TREQ_COUNT
        cmp #$03
        beq :+
        jmp cancel_invalid
:
        lda _udeks_lifecycle_current_private
        beq cancel_missing
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_RUNNING
        bne cancel_invalid
        ; Task ids are 16-bit. Reject the high byte before interpreting the
        ; low byte as the zero selector, the caller, or a child slot.
        lda TREQ_PAYLOAD+1
        bne cancel_missing
        lda TREQ_PAYLOAD
        beq cancel_invalid
        cmp _udeks_lifecycle_current_private
        beq cancel_invalid
        cmp #TASK_COUNT+1
        bcs cancel_missing
        sec
        sbc #$01
        tay
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        beq cancel_missing
        cmp #TASK_STATE_ZOMBIE
        beq cancel_missing
        lda _udeks_lifecycle_slots_private+TASK_SLOT_PARENT,x
        cmp _udeks_lifecycle_current_private
        bne cancel_missing

        lda TREQ_PAYLOAD+2
        sta _udeks_lifecycle_slots_private+TASK_SLOT_EXIT,x
        lda #$00
        sta _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        sta _udeks_lifecycle_slots_private+TASK_SLOT_RESUME,x
        sta _udeks_task_wait_state_private,y
        sta _udeks_task_wait_operation_private,y
        sta _udeks_task_wait_sequence_private,y
        sta _udeks_task_wait_descriptor_private,y
        sta _udeks_task_wait_count_private,y
        sta _udeks_task_wait_flags_private,y
        sta _udeks_task_wait_selector_private,y
        sta _udeks_task_wait_selector_high_private,y
        sta _udeks_task_wait_child_private,y
        sta _udeks_task_wait_status_private,y
        lda #TASK_STATE_ZOMBIE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #LIFECYCLE_CANCEL
        sta _udeks_lifecycle_last_event_private
        lda #$00
        jmp _udeks_bootfs_finish_ok

cancel_missing:
        inc _udeks_lifecycle_rejected_private
        lda #ERR_ESRCH
        jmp _udeks_bootfs_finish_error
cancel_invalid:
        inc _udeks_lifecycle_rejected_private
        lda #ERR_EINVAL
        jmp _udeks_bootfs_finish_error

; Called once per resident service pass before task selection. SLEEP/POLL deadlines are
; 16-bit modulo values; the ABI's 600-tick bound keeps signed subtraction
; unambiguous across wrap. The raster IRQ owns the 60 Hz logical counter.
_udeks_task_sleep_poll:
        php
        sei
        ldx #$00
        ldy #$00
sleep_poll_next:
        lda _udeks_task_wait_state_private,y
        cmp #WAIT_BLOCKED
        jne sleep_poll_advance
        lda _udeks_task_wait_operation_private,y
        cmp #OP_POLL
        beq input_poll
        cmp #OP_SLEEP
        jne sleep_poll_advance
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_WAITING
        jne sleep_poll_advance
        lda _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        cmp #WAIT_TIMER
        bne sleep_poll_advance
        sec
        lda _udeks_monotonic_ticks_low
        sbc _udeks_task_wait_selector_private,y
        lda _udeks_monotonic_ticks_high
        sbc _udeks_task_wait_selector_high_private,y
        bmi sleep_poll_advance
        jmp wake_waiter
input_poll:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        cmp #WAIT_INPUT
        bne sleep_poll_advance
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_WAITING
        beq input_waiting
        cmp #TASK_STATE_STOPPED
        bne sleep_poll_advance
        lda _udeks_lifecycle_slots_private+TASK_SLOT_RESUME,x
        cmp #TASK_STATE_WAITING
        bne sleep_poll_advance
input_waiting:
        lda _udeks_line_editor_submitted_ready_value
        beq input_timeout
        lda #$01
        bne input_ready
input_timeout:
        lda _udeks_task_wait_child_private,y
        and _udeks_task_wait_status_private,y
        cmp #$ff
        beq sleep_poll_advance           ; infinite wait has no deadline
        sec
        lda _udeks_monotonic_ticks_low
        sbc _udeks_task_wait_selector_private,y
        lda _udeks_monotonic_ticks_high
        sbc _udeks_task_wait_selector_high_private,y
        bmi sleep_poll_advance
        lda #$00
input_ready:
        sta _udeks_task_wait_flags_private,y
wake_waiter:
        lda #WAIT_READY
        sta _udeks_task_wait_state_private,y
        lda #$00
        sta _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_STOPPED
        bne wake_running
        lda #TASK_STATE_RUNNABLE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_RESUME,x
        bne wake_record
wake_running:
        lda #$00
        sta _udeks_lifecycle_slots_private+TASK_SLOT_RESUME,x
        lda #TASK_STATE_RUNNABLE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
wake_record:
        lda #$06                       ; LIFECYCLE_UNBLOCK
        sta _udeks_lifecycle_last_event_private
sleep_poll_advance:
        txa
        clc
        adc #TASK_SLOT_STRIDE
        tax
        iny
        cpy #TASK_COUNT
        jne sleep_poll_next
        plp
        lda #$00
        rts

; Called once per video frame from the pointer IRQ through fixed scheduler
; gate $C906. NTSC advances once; PAL distributes six logical 60 Hz ticks
; over five 50 Hz frames (1,1,1,1,2).
_udeks_task_tick_advance:
        lda CAPABILITY_VIDEO
        cmp #$01
        bne monotonic_one_tick
        lda tick_fraction
        clc
        adc #$06
        cmp #$0a
        bcc monotonic_pal_one
        sec
        sbc #$0a
        sta tick_fraction
        jsr increment_monotonic
        jsr increment_monotonic
        rts
monotonic_pal_one:
        sec
        sbc #$05
        sta tick_fraction
monotonic_one_tick:
        jsr increment_monotonic
        rts

increment_monotonic:
        inc _udeks_monotonic_ticks_low
        bne :+
        inc _udeks_monotonic_ticks_high
:
        rts

        .segment "BSS"
_udeks_task_wait_state_private:       .res TASK_COUNT
_udeks_task_wait_operation_private:   .res TASK_COUNT
_udeks_task_wait_sequence_private:    .res TASK_COUNT
_udeks_task_wait_descriptor_private:  .res TASK_COUNT
_udeks_task_wait_count_private:       .res TASK_COUNT
_udeks_task_wait_flags_private:       .res TASK_COUNT
_udeks_task_wait_selector_private:    .res TASK_COUNT
_udeks_task_wait_selector_high_private: .res TASK_COUNT
_udeks_task_wait_child_private:       .res TASK_COUNT
_udeks_task_wait_status_private:      .res TASK_COUNT
tick_fraction:                        .res 1
_udeks_monotonic_ticks_low:           .res 1
_udeks_monotonic_ticks_high:          .res 1
