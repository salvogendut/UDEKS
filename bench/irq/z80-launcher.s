; SPDX-License-Identifier: GPL-3.0-or-later
;
; 8502 bootstrap for the Z80 IM1 probe. It makes the bottom and top 16 KiB
; common, then replaces the dormant reset-time Z80 continuation at $FFED.

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
        .byte $3e, $7e             ; LD A,$7E: bank 1, normal low RAM
        .byte $32, $00, $ff        ; LD ($FF00),A
        .byte $c3, $00, $28        ; JP $2800

        ; $27D0 + 48 bytes = the Z80 payload's linked address $2800.
        .res 15, $ea
        .incbin "build/bench/irq/z80/irq-z80.bin"
