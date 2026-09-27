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
        .import _udeks_ush_poll
        .import _submit_request
        .import decsp2
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
