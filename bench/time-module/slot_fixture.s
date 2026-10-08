; SPDX-License-Identifier: GPL-3.0-or-later
; Execute the real startup veneer and candidate manager, with a deliberately
; recursive startup fixture. Header words are private simulator addresses.
        .import _udeks_service_start_all, _udeks_service_start_phase
        .import _udeks_service_start_result, _udeks_time_slot_state
        .import _udeks_time_slot_control, _udeks_time_slot_poll, _udeks_time_slot_set
        .import time_slot_validate
        .import _udeks_time_now, pushax
        .importzp tmp1, tmp2
        .export _udeks_service_start_all_once
        .segment "HEADER"
        .addr _udeks_service_start_all, _udeks_service_start_phase
        .addr _udeks_service_start_result, calls, desired, seen_phase
        .addr recursive_result, begin_result, _udeks_time_slot_control
        .addr _udeks_time_slot_poll, _udeks_time_slot_set, _udeks_time_slot_state
        .addr validate_only, poison_stack
        .addr legacy_read
        .segment "DATA"
calls: .byte 0
desired: .byte 0
seen_phase: .byte 0
recursive_result: .byte 0
begin_result: .byte 0
        .segment "CODE"
_udeks_service_start_all_once:
        inc calls
        lda _udeks_service_start_phase
        sta seen_phase
        jsr _udeks_service_start_all
        sta recursive_result
        lda #1
        jsr _udeks_time_slot_control
        sta begin_result
        lda desired
        ldx #0
        rts
validate_only:
        stx tmp1
        sty tmp2
        jsr time_slot_validate
        lda #0
        rol a
        ldx #0
        rts
poison_stack:
        ; Repeat startup with no usable cc65 stack. Restore the harness's
        ; known root SP afterward; the private latch must not dereference it.
        lda #0
        sta $06
        sta $07
        jsr _udeks_service_start_all
        pha
        lda $06
        ora $07
        beq stack_intact
        pla
        lda #$ee
        pha
stack_intact:
        lda #$ef
        sta $07
        pla
        rts
legacy_read:
        ; Real published C ABI: hour/minute pointers on the cc65 stack,
        ; second pointer in AX, callee removes all six argument bytes.
        lda #<$f130
        ldx #>$f130
        jsr pushax
        lda #<$f131
        ldx #>$f131
        jsr pushax
        lda #<$f132
        ldx #>$f132
        jsr _udeks_time_now
        lda #0
        rts
