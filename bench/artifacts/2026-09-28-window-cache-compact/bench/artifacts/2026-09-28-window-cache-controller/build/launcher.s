; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .import _main, __BSS_RUN__, __BSS_SIZE__
        .importzp sp, ptr1
        .export __STARTUP__ : absolute = 1
        .export _raster_timer_start, _raster_timer_stop
        .segment "STARTUP"
entry:
        sei
        cld
        ldx #$ff
        txs
        lda #$3e
        sta $ff00
        lda #$00
        sta $d030              ; stock 1 MHz, no display/sprite bus steals
        sta $d015
        sta $d01a
        sta $dc0e
        sta $dc0f
        lda #$0b
        sta $d011
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$00
        sta $d508
        sta $d507              ; native page zero
        sta $d50a
        lda #$01
        sta $d509              ; native hardware stack
        lda #$09
        sta $d506
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
idle:
        jmp idle

        .segment "CODE"
_raster_timer_start:
        lda #$00
        sta $dc0e
        sta $dc0f
        lda #$ff
        sta $dc04
        sta $dc05
        sta $dc06
        sta $dc07
        lda #$51               ; B: count A underflows, load and start
        sta $dc0f
        lda #$11               ; A: Phi2, load and start
        sta $dc0e
        rts
_raster_timer_stop:
        lda #$00
        sta $dc0e              ; stop A before B; drain underflow pipeline
        nop
        nop
        sta $dc0f
        lda $dc04
        eor #$ff
        sta $7fc8
        lda $dc05
        eor #$ff
        sta $7fc9
        lda $dc06
        eor #$ff
        sta $7fca
        lda $dc07
        eor #$ff
        sta $7fcb
        rts
