; SPDX-License-Identifier: GPL-3.0-or-later
;
; Combined loader for the bidirectional offload crossover sweep.

        .setcpu "6502"
        .segment "CODE"

        ; BASIC 7.0 line 10: SYS 10192 ($27D0).
basic_start:
        .word basic_end
        .word 10
        .byte $9e
        .byte "10192", 0
basic_end:
        .word 0
        .res $0bc2, $00

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
        lda #$b0
        sta $d505
        jmp $2800

z80_patch:
        .byte $3e, $7e
        .byte $32, $00, $ff
        .byte $c3, $00, $30

        .res 10, $ea
        .incbin "build/bench/offload/8502/offload-8502.bin"
        .incbin "build/bench/offload/z80/offload-z80.bin"
