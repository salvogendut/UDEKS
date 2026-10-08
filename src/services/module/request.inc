; SPDX-License-Identifier: GPL-3.0-or-later
; Candidate UTRQ 0.19 / operation 28. The storage router supplies the trusted
; context tag in A, NEVER a caller-provided ownership field. Only tag 9 (the
; serialized synchronous foreground invocation) may control the time slot.
; Included by the real syscall gate and the CPU fixture.
        .import _udeks_time_slot_control, _udeks_time_slot_state
        .import _udeks_time_slot_reset

.macro time_module_abort_body
        ; Private CF33 entry: trusted foreground retirement, no C runtime.
        lda _udeks_time_slot_state
        cmp #1
        bne :+
        jmp _udeks_time_slot_reset
:       rts
.endmacro

.macro time_module_reply_body
        lda _udeks_time_slot_state
        sta $f367
        lda #1
        jmp _udeks_bootfs_finish_ok
.endmacro

.macro time_module_request_body
        .local invalid, error
        cmp #9
        bne invalid
        lda $f35e                  ; require the new request version
        cmp #19
        bne invalid
        lda $f362                  ; descriptor and flags are reserved
        ora $f366
        bne invalid
        lda $f363
        cmp #3
        bne invalid
        lda $f367                  ; action; count word ignored except COMMIT
        ldx $f368
        ldy $f369
        jsr _udeks_time_slot_control
        bne error
        jmp time_module_reply
invalid:
        lda #22
error:
        jmp _udeks_bootfs_finish_error
.endmacro
