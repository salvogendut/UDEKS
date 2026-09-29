; SPDX-License-Identifier: GPL-3.0-or-later
;
; Combined 8502/Z80 ownership-transfer benchmark image. Bottom and top 16 KiB
; are common RAM, so both processors execute their half without copying code.

        .setcpu "6502"
        .segment "CODE"

        ; BASIC 7.0 line 10: SYS 10192 ($27D0). This lets an automated run use
        ; RUN"*" so loading and execution are sequenced by BASIC itself.
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

        ; Wake the Z80 at its reset-BIOS continuation. It initializes at $3000,
        ; returns ownership, and this processor resumes at the following JMP.
        lda #$b0
        sta $d505
        jmp $2800

z80_patch:
        .byte $3e, $7e             ; LD A,$7E: bank 1, normal low RAM
        .byte $32, $00, $ff        ; LD ($FF00),A
        .byte $c3, $00, $30        ; JP $3000

        ; $27D0 + 48 bytes = the 8502 controller's linked address $2800.
        .res 10, $ea
        .incbin "build/bench/handoff/8502/handoff-8502.bin"
        .incbin "build/bench/handoff/z80/handoff-z80.bin"
