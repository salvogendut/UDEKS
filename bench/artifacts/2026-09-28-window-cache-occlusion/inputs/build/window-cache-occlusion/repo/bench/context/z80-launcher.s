; SPDX-License-Identifier: GPL-3.0-or-later
;
; 8502 bootstrap for the Z80 task-context benchmark.

        .setcpu "6502"
        .segment "CODE"

launcher:
        sei
        lda #$3e
        sta $ff00
        lda #$0f
        sta $d506
        ldx #$07
copy_patch:
        lda z80_patch,x
        sta $ffed,x
        dex
        bpl copy_patch
        jmp $ffd0

z80_patch:
        .byte $3e, $7e
        .byte $32, $00, $ff
        .byte $c3, $00, $28

        .res 15, $ea
        .incbin "build/bench/context/z80/context-z80.bin"
