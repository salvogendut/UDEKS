; SPDX-License-Identifier: GPL-3.0-or-later
; Executes ONLY from bank 1 with IRQs masked. All imports are fixed common
; gateways/parameters; no cc65 runtime or kernel-code dependency.
        .setcpu "6502"
        .include "layout.inc"
        .export core_start, core_end
        .segment "OVERLAY"
core_start:
        jsr READ
        lda ADDRESS
        sta cache_read+1
        sta cache_write+1
        lda ADDRESS+1
        sta cache_read+2
        sta cache_write+2
        ldx #$00
        lda MODE
        bne paste_setup
capture:
        lda #$00
        sta second
        txa
        clc
        adc #$01
        cmp RAWCOUNT
        bcs no_next
        lda STAGE+1,x
        sta second
no_next:
        lda STAGE,x
        ldy SHIFT
        beq packed
left:
        asl second
        rol a
        dey
        bne left
packed:
        inx
        cpx STRIDE
        bne full_byte
        and LASTMASK
        sta PARAM+9             ; expose packed tail for independent driver check
full_byte:
        dex
cache_write:
        sta $ffff,x
        inx
        cpx STRIDE
        bcc capture
        rts
paste_setup:
        lda #$ff
        sta mask1
        lda #$00
        sta mask2
        ldy SHIFT
        beq paste
body_masks:
        lsr mask1
        ror mask2
        dey
        bne body_masks
paste:
        lda #$00
        sta second
cache_read:
        lda $ffff,x
        ldy SHIFT
        beq split
right:
        lsr a
        ror second
        dey
        bne right
split:
        sta first
        inx
        cpx STRIDE
        bne merge
        lda LASTMASK
        sta mask1
        lda #$00
        sta mask2
        ldy SHIFT
        beq merge
tail_masks:
        lsr mask1
        ror mask2
        dey
        bne tail_masks
merge:
        dex
        lda STAGE,x
        eor first
        and mask1
        eor STAGE,x
        sta STAGE,x
        lda mask2
        beq next
        lda STAGE+1,x
        eor second
        and mask2
        eor STAGE+1,x
        sta STAGE+1,x
next:
        inx
        cpx STRIDE
        bcc paste
        jmp WRITE
first:  .byte 0
second: .byte 0
mask1:  .byte 0
mask2:  .byte 0
core_end:
        .assert core_start = CORE, error, "cache overlay entry moved"
        .assert core_end <= CACHE, error, "overlay reaches packed cache"
