; SPDX-License-Identifier: GPL-3.0-or-later
; Bank-0 filesystem fallback. IRQ-masked, synchronous first implementation.
; The overlay stays BELOW the transient C stack at $F700, unlike VIC gateways.
        .setcpu "6502"
        .segment "CODE"
router:
        php
        sei
        lda #0
        sta $f3ed                   ; invalidate the VIC outline overlay lease
        ldx #gateway_end-gateway-1
copy:   lda gateway,x
        sta $f68a,x
        dex
        bpl copy
        jsr $f68a
        plp
        cmp #0
        beq fallback
        lda #0
        clc
        rts
fallback:
        jmp $f3ef                   ; unchanged bootfs/lifecycle fallback
gateway:
        cld
        ldx #29
save:   lda $02,x
        pha
        dex
        bpl save
        sta $ff03                   ; bank-1 worker I/O
        lda #<$e200
        sta $02
        lda #>$e200
        sta $03
        jsr $1200
        sta $f68a+(result+1-gateway)
        sta $ff01                   ; bank-0 kernel I/O
        ldx #0
restore:
        pla
        sta $02,x
        inx
        cpx #30
        bcc restore
result: lda #0
        rts
gateway_end:
        .assert router = $c880, lderror, "storage router moved"
        .assert * <= $c900, lderror, "storage router reaches lifecycle handler"
        .assert $f68a+gateway_end-gateway <= $f700, error, "storage gateway reaches transient stack"
