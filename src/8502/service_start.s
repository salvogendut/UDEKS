; SPDX-License-Identifier: GPL-3.0-or-later
;
; Stack-independent one-shot veneer for service startup. Application slot 1
; is reused after hardware discovery, so a repeated call must return before
; compiled C adjusts or reads the currently active cc65 software stack.

        .setcpu "6502"

        .import _udeks_service_start_all_once
        .export _udeks_service_start_all
        .export _udeks_service_start_phase, _udeks_service_start_result

        .segment "CODE"
_udeks_service_start_all:
attempted:
        lda #$00
        bne completed
        ; Private, monotonic latch in the RAM-resident veneer. Diagnostic
        ; corruption (or a failed start) must never re-enter retired code.
        ; Phase 1 also rejects recursion while the startup frame is live.
        inc attempted+1
        jsr _udeks_service_start_all_once
        sta cached_result+1
        inc attempted+1             ; phase 2 only AFTER the frame returns
completed:
cached_result:
        lda #$01                    ; reentrant call returns a nonzero result
        ldx #$00
        rts
_udeks_service_start_phase = attempted+1
_udeks_service_start_result = cached_result+1
