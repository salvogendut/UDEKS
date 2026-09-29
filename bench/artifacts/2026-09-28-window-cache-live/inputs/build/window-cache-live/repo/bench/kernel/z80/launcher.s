; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .segment "CODE"

launcher:
        sei
        lda #$3e
        sta $ff00
        lda #$c3
        sta $ffed
        lda #$00
        sta $ffee
        lda #$20
        sta $ffef
        lda #$03
        sta $f186               ; stock Z80 configuration
        jmp $ffd0

        .res 3, $ea
        .incbin "build/bench/kernel/z80/kernel-z80.bin"
