; SPDX-License-Identifier: GPL-3.0-or-later
;
; Per-task ownership for lifecycle requests that outlive the shared $F359
; record. The request handler snapshots blocking WAITPID/SLEEP here, EXIT
; turns a matching child wait into a ready response, CANCEL discards a dead
; task's snapshot, and context selection publishes before restoring a task.

        .setcpu "6502"

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
        .export _udeks_monotonic_ticks_low
        .export _udeks_monotonic_ticks_high
        .import _udeks_lifecycle_current_private
        .import _udeks_lifecycle_last_event_private
        .import _udeks_lifecycle_rejected_private
        .import _udeks_lifecycle_slots_private
        .import _udeks_bootfs_finish_error
        .import _udeks_bootfs_finish_ok

TASK_COUNT              = $08
WAIT_READY              = $02
OP_SLEEP                = $0d
OP_CANCEL               = $0e
WAIT_BLOCKED            = $01
WAIT_TIMER              = $03
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
TASK_STATE_ZOMBIE       = $06
LIFECYCLE_CANCEL        = $0b
ERR_ESRCH               = $03
ERR_EINVAL              = $16

TREQ_BASE               = $f359
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

_udeks_task_wait_publish_current:
        lda _udeks_lifecycle_current_private
        beq publish_done
        tax
        dex
        lda _udeks_task_wait_state_private,x
        cmp #WAIT_READY
        bne publish_done

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
        cmp TREQ_PAYLOAD
        beq cancel_invalid
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_RUNNING
        bne cancel_invalid
        lda TREQ_PAYLOAD
        beq cancel_invalid
        lda TREQ_PAYLOAD+1
        bne cancel_missing
        lda TREQ_PAYLOAD
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

; Called once per resident service pass before task selection. Deadlines are
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
        bne sleep_poll_advance
        lda _udeks_task_wait_operation_private,y
        cmp #OP_SLEEP
        bne sleep_poll_advance
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_WAITING
        bne sleep_poll_advance
        lda _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        cmp #WAIT_TIMER
        bne sleep_poll_advance
        sec
        lda _udeks_monotonic_ticks_low
        sbc _udeks_task_wait_selector_private,y
        lda _udeks_monotonic_ticks_high
        sbc _udeks_task_wait_selector_high_private,y
        bmi sleep_poll_advance
        lda #WAIT_READY
        sta _udeks_task_wait_state_private,y
        lda #$00
        sta _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        sta _udeks_lifecycle_slots_private+TASK_SLOT_RESUME,x
        lda #TASK_STATE_RUNNABLE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #$06                       ; LIFECYCLE_UNBLOCK
        sta _udeks_lifecycle_last_event_private
sleep_poll_advance:
        txa
        clc
        adc #TASK_SLOT_STRIDE
        tax
        iny
        cpy #TASK_COUNT
        bne sleep_poll_next
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
