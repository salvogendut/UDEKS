; SPDX-License-Identifier: GPL-3.0-or-later
; sim6502 harness only: run the EXACT independently linked module with the
; resident's ZP convention, not the simulator program's compiler runtime.
        .export _module_call, _module_entry, _module_hour, _module_minute, _module_second
        .export _module_stack_error
        .segment "BSS"
saved: .res 32
result: .res 1
_module_entry: .res 2
_module_hour: .res 1
_module_minute: .res 1
_module_second: .res 1
_module_stack_error: .res 1

        .segment "CODE"
_module_call:
        ldx #31
save:
        lda $00,x
        sta saved,x
        dex
        bpl save
        lda #0
        sta _module_stack_error
        sta $06
        lda #$ef
        sta $07
        lda _module_entry
        sta call+1
        lda _module_entry+1
        sta call+2
        cld
        lda _module_hour
        ldx _module_minute
        ldy _module_second
call:   jsr $ffff
        sta result
        lda $06
        bne stack_bad
        lda $07
        cmp #$ef
        beq restore_begin
stack_bad:
        inc _module_stack_error
restore_begin:
        ldx #31
restore:
        lda saved,x
        sta $00,x
        dex
        bpl restore
        lda result
        ldx #0
        rts
