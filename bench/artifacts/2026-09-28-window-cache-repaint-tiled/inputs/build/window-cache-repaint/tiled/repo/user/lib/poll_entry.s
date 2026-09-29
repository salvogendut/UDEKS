; SPDX-License-Identifier: GPL-3.0-or-later
;
; Persistent UDEX entry. Once the production switch tail is activated this
; loop never returns through an unseeded initial hardware stack: each bounded
; shell poll explicitly yields and later resumes inside the request call.

        .setcpu "6502"
        .segment "STARTUP"

        .export _udeks_task_poll_entry
        .export _udeks_submit_simple
        .export _udeks_yield
        .export _udeks_poll
        .export _udeks_write_byte
        .import _udeks_ush_poll
        .import _submit_request
        .import decsp2
        .import incsp1
        .importzp sp

_udeks_task_poll_entry:
        jsr _udeks_ush_poll
        jsr _udeks_yield
        jmp _udeks_task_poll_entry

; Compact leaf wrapper for zero-payload requests. Keeping it in assembly
; recovers enough bootfs space for YIELD without growing the disk contract.
_udeks_yield:
        lda #$0a
_udeks_submit_simple:
        tax
        jsr decsp2
        txa
        ldy #$01
        sta (sp),y
        lda #$00
        dey
        sta (sp),y
        jmp _submit_request

; cc65 supplies the timeout in AX, descriptor on its software stack.
; Preserve that stack across the blocking request, not in shared scratch.
_udeks_poll:
        sta $f369
        stx $f36a
        lda #$01
        sta $f367
        lda #$00
        sta $f368
        lda #$10
        ldx #$04
        bne submit_descriptor

_udeks_write_byte:
        sta $f367
        lda #$02
        ldx #$01
        jsr submit_descriptor
        cmp #$01
        beq :+
        lda #$01
        bne :++
:       lda #$00
:
        ldx #$00
        rts

; A=operation, X=count; the descriptor is the existing stack argument.
submit_descriptor:
        pha
        txa
        pha
        jsr decsp2
        pla
        tax
        pla
        ldy #$01
        sta (sp),y
        iny
        lda (sp),y
        ldy #$00
        sta (sp),y
        txa
        jsr _submit_request
        jmp incsp1
