; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .export _udeks_program_entry, _probe_request
        .import _udeks_program_main, pusha
        .import _probe_operation, _probe_sequence, _probe_error, _probe_low_sp
        .importzp ptr1, tmp1, sp
        .segment "STARTUP"
        nop                         ; prove non-base entry from the UDEX header
        nop
_udeks_program_entry:
        sta tmp1
        stx ptr1
        sty ptr1+1
        jsr pusha
        lda ptr1
        ldx ptr1+1
        jmp _udeks_program_main
        .segment "CODE"
_probe_request:
        sta _probe_operation
        lda sp+1
        cmp _probe_low_sp+1
        bcc lower
        bne request
        lda sp
        cmp _probe_low_sp
        bcs request
lower:  lda sp
        sta _probe_low_sp
        lda sp+1
        sta _probe_low_sp+1
request:
        ldx #5
copy:   lda signature,x
        sta $f359,x
        dex
        bpl copy
        lda #0
        sta $f362                   ; descriptor
        sta $f366                   ; flags
        sta $f363                   ; YIELD count = 0
        sta $f368                   ; SLEEP ticks high
        lda #2
        sta $f367                   ; SLEEP ticks low
        lda _probe_operation
        cmp #13
        bne :+
        lda #2
        sta $f363
:       lda _probe_operation
        sta $f360
        inc _probe_sequence
        lda _probe_sequence
        sta $f361
        lda #1
        sta $f35f
        jsr $ff16
        ; SLEEP must republish this caller's original response sequence.
        lda _probe_operation
        cmp #13
        bne done
        lda $f361
        cmp _probe_sequence
        bne failed
        lda $f35f
        cmp #2
        bne failed
        lda $f365
        beq done
failed: lda #4
        sta _probe_error
done:   rts
        .segment "RODATA"
signature: .byte "UTRQ",0,8
