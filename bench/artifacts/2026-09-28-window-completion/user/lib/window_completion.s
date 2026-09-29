; SPDX-License-Identifier: GPL-3.0-or-later
; Opt-in UAPP 0.3 helper; do not add its code to clients that never use it.
; An older kernel returns INVALID without interpreting reserved header bytes.
        .setcpu "6502"
        .export _udeks_window_image_complete
        .segment "CODE"
_udeks_window_image_complete:
        tay
        lda $cf54
        bne no_completion
        lda $cf55
        cmp #$03
        bcc no_completion
        tya
        jmp ($cf58)
no_completion:
        lda #$01
        ldx #$00
        rts
