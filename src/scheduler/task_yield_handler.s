; SPDX-License-Identifier: GPL-3.0-or-later
;
; Runtime replacement for the scheduler's one-shot bootstrap prefix. The
; common switch tail has already captured the task CPU/MMU context before
; entering here. A successful YIELD publishes its synchronous response, marks
; the task runnable, and returns carry set so the common tail suspends it.

        .setcpu "6502"

        .export _udeks_task_yield_handler
        .import _udeks_task_context_save_current
        .import _udeks_lifecycle_slots_private
        .import _udeks_lifecycle_current_private
        .import _udeks_lifecycle_last_event_private
        .import _udeks_bootfs_finish_error

TREQ_BASE               = $f359
TREQ_STATE              = TREQ_BASE+$06
TREQ_DESCRIPTOR         = TREQ_BASE+$09
TREQ_COUNT              = TREQ_BASE+$0a
TREQ_RESULT             = TREQ_BASE+$0b
TREQ_ERROR              = TREQ_BASE+$0c
TREQ_FLAGS              = TREQ_BASE+$0d

TREQ_COMPLETE           = $02
ERR_EINVAL              = $16

TASK_STATE_OFFSET       = $01
TASK_STATE_RUNNABLE     = $02
LIFECYCLE_YIELD         = $04

        .segment "YIELDHANDLER"

_udeks_task_yield_handler:
        lda TREQ_DESCRIPTOR
        ora TREQ_COUNT
        ora TREQ_FLAGS
        bne yield_invalid

        jsr _udeks_task_context_save_current
        lda #LIFECYCLE_YIELD
        sta _udeks_lifecycle_last_event_private
        lsr a                           ; RUNNABLE = 2
        sta _udeks_lifecycle_slots_private+TASK_STATE_OFFSET
        sta TREQ_STATE
        lsr a
        lsr a                           ; NONE = 0
        sta _udeks_lifecycle_current_private
        sta TREQ_RESULT
        sta TREQ_ERROR
        sec
        rts

yield_invalid:
        lda #ERR_EINVAL
        jmp _udeks_bootfs_finish_error

yield_handler_end:
        .assert _udeks_task_yield_handler = $1c00, error, "YIELD handler moved"
        .assert yield_handler_end <= $1c2e, error, "YIELD handler reaches live scheduler code"
