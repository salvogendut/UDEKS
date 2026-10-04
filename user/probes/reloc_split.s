; SPDX-License-Identifier: GPL-3.0-or-later
; Real split low/high symbol references, plus an absolute common-RAM pointer.
        .setcpu "6502"
        .export _probe_split_ok
        .import _probe_value, _probe_progress
        .segment "CODE"
_probe_split_ok:
        ldx #0
        lda low_bytes
        cmp #<_probe_value
        bne failed
        lda low_bytes+1
        cmp #<_probe_progress
        bne failed
        lda high_bytes
        cmp #>_probe_value
        bne failed
        lda high_bytes+1
        cmp #>_probe_progress
        bne failed
        lda absolute_address
        cmp #$16
        bne failed
        lda absolute_address+1
        cmp #$ff
        bne failed
        lda #1
        rts
failed: lda #0
        rts
        .segment "RODATA"
low_bytes: .lobytes _probe_value, _probe_progress
high_bytes: .hibytes _probe_value, _probe_progress
absolute_address: .word $ff16
