; SPDX-License-Identifier: GPL-3.0-or-later
;
; Per-task ownership for lifecycle requests that outlive the shared $F359
; record.  The request handler snapshots a blocking WAITPID here, EXIT turns
; the matching snapshot into a ready response, and task-context selection
; publishes that response immediately before restoring the parent.

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
        .import _udeks_lifecycle_current_private

TASK_COUNT              = $08
WAIT_READY              = $02

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
        lda #$01
        sta TREQ_RESULT
        lda #$00
        sta TREQ_ERROR
        lda _udeks_task_wait_flags_private,x
        sta TREQ_FLAGS
        lda _udeks_task_wait_child_private,x
        sta TREQ_PAYLOAD
        lda _udeks_task_wait_selector_high_private,x
        sta TREQ_PAYLOAD+1
        lda _udeks_task_wait_status_private,x
        sta TREQ_PAYLOAD+2
        lda #$00
        sta TREQ_PAYLOAD+3
        sta _udeks_task_wait_state_private,x
        ; State is the publication commit byte and must be written last.
        lda #TREQ_COMPLETE
        sta TREQ_STATE
publish_done:
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
