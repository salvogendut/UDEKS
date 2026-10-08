; SPDX-License-Identifier: GPL-3.0-or-later
; Only environment stubs / observation live here. CF30, its envelope checks,
; the C880 ownership/retirement router, finish handlers, module manager and
; the independent console SDK are the production candidate instructions.
        .import _udeks_service_start_all, _udeks_service_start_phase, _udeks_service_start_result
        .import _udeks_time_slot_state, _udeks_time_slot_poll, _udeks_time_slot_set
        .import test_sdk_entry
        .export _udeks_service_start_all_once, test_trap
        .export __SERVICEBOOT_RUN__ = $93d0, __SERVICEBOOT_SIZE__ = 518
        .segment "HEADER"
        .addr _udeks_service_start_all, _udeks_service_start_phase, _udeks_service_start_result
        .addr _udeks_time_slot_state, _udeks_time_slot_poll, _udeks_time_slot_set
        .addr sdk_probe, sdk_bad, transport, retired_tag, retire_count, storage_count
        .segment "BSS"
saved: .res 32
sdk_bad: .res 1
sdk_result: .res 1
arg: .res 1
count: .res 2
retired_tag: .res 1
retire_count: .res 1
storage_count: .res 1
        .segment "CODE"
_udeks_service_start_all_once:
        lda #0
        tax
        rts
test_trap:
        brk                         ; an unrelated kernel service was called
transport:
        cpy #$12
        bne storage
        sta retired_tag
        inc retire_count
        lda #0
        rts
storage:
        inc storage_count
        lda #0                      ; unhandled -> real bootfs fallback
        rts
sdk_probe:
        ; Save harness root ZP, then impersonate a private console runtime.
        sta arg
        stx count
        sty count+1
        ldx #31
save:   lda $00,x
        sta saved,x
        txa
        ora #$a0
        sta $00,x
        dex
        bpl save
        lda arg
        sta $e7ff                   ; first C argument on private stack
        lda #$ff
        sta $02
        lda #$e7
        sta $03
        lda #0
        sta sdk_bad
        ; Poison the tempting WRONG root SP ($A7A6, from seeded $06/$07).
        ; A missing private->root stack bridge must not pass just because
        ; simulator RAM happens to be writable there.
        lda #$3c
        ldx #127
guard:  sta $a780,x
        dex
        bpl guard
        lda count
        ldx count+1
        sed                         ; veneer must normalize, then restore D
        jsr test_sdk_entry
        sta sdk_result
        php
        pla
        and #8
        bne :+
        inc sdk_bad
:       cld
        lda $02
        bne bad
        lda $03
        cmp #$e8
        bne bad
        ldx #31
compare:
        cpx #2
        beq next
        cpx #3
        beq next
        txa
        ora #$a0
        cmp $00,x
        beq next
bad:    inc sdk_bad
        jmp restore_begin
next:   dex
        bpl compare
        ldx #127
stack_guard:
        lda $a780,x
        cmp #$3c
        bne bad
        dex
        bpl stack_guard
restore_begin:
        ldx #31
restore:
        lda saved,x
        sta $00,x
        dex
        bpl restore
        lda sdk_result
        rts
