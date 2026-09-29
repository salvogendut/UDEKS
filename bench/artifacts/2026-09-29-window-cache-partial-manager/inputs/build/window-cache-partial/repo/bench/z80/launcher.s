; SPDX-License-Identifier: GPL-3.0-or-later
;
; Entered by the 8502 at $1FE0 after BASIC loads the combined PRG. It selects
; RAM with I/O visible, replaces the dormant Z80 continuation with JP $2000,
; then uses Commodore's reset-installed ownership handoff at $FFD0.

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
        sta $f106
        jmp $ffd0

        ; Keep the Z80 payload's linked entry at $2000.
        .res 3, $ea
        .incbin "build/bench/z80/bench-z80.bin"
