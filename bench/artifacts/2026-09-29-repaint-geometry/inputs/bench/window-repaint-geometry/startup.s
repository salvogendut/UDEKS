; SPDX-License-Identifier: GPL-3.0-or-later
; Standalone flat-RAM diagnostic only. Never enters a production UDEKS image.
        .setcpu "6502"
        .import _main, __BSS_RUN__, __BSS_SIZE__
        .importzp sp, ptr1
        .export __STARTUP__ : absolute = 1
        .segment "STARTUP"
        sei
        cld
        ldx #$ff
        txs
        lda #$3e
        sta $ff00
        lda #<$eff0
        sta sp
        lda #>$eff0
        sta sp+1
        lda #<__BSS_RUN__
        sta ptr1
        lda #>__BSS_RUN__
        sta ptr1+1
        ldx #>__BSS_SIZE__
        ldy #$00
        lda #$00
        cpx #$00
        beq tail
page:
        sta (ptr1),y
        iny
        bne page
        inc ptr1+1
        dex
        bne page
tail:
        ldy #<__BSS_SIZE__
        beq run
clear:
        dey
        sta (ptr1),y
        bne clear
run:
        jsr _main
forever:
        jmp forever
