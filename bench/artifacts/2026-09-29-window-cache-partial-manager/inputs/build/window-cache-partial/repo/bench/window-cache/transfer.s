; SPDX-License-Identifier: GPL-3.0-or-later
; Separate prototype overlay in the existing VIC gateway reservation. It is
; never installed in production. $F380 parameters and $F400 staging are
; borrowed cooperatively; IRQs must not dispatch services while borrowed.
        .setcpu "6502"
        .export _cache_transfer, _cache_seed_service
        .export _cache_gateway_size
        .segment "CODE"
RUN = $f68a
ADDRESS = $f380
COUNT = $f382
MODE = $f383
STAGE = $f400
KERNEL = $ff01
WORKER = $ff04

_cache_seed_service:
        lda #$03
        bne _cache_transfer
_cache_transfer:
        pha
        lda #$00
        sta $f3ed             ; invalidate resident outline-gateway tag
        ldx #$00
install:
        lda gateway,x
        sta RUN,x
        inx
        cpx #gateway_end-gateway
        bne install
        pla
        sta MODE
        jsr RUN
        rts

gateway:
        lda #$00
        sta WORKER
        lda MODE
        cmp #$02
        beq release
        cmp #$03
        beq seed
        lda ADDRESS
        sta RUN+(read-gateway)+1
        sta RUN+(write-gateway)+1
        lda ADDRESS+1
        sta RUN+(read-gateway)+2
        sta RUN+(write-gateway)+2
        ldy #$00
        lda MODE
        bne read_loop
write_loop:
        lda STAGE,y
write:  sta $ffff,y
        iny
        cpy COUNT
        bne write_loop
        beq done
read_loop:
read:   lda $ffff,y
        sta STAGE,y
        iny
        cpy COUNT
        bne read_loop
        beq done
release:
        ldy #$00
restore:
        lda $4000,y
        sta STAGE,y
        iny
        bne restore
        beq done
seed:
        ldy #$00
save:
        lda STAGE,y
        sta $4000,y
        iny
        bne save
done:
        lda #$00
        sta KERNEL
        rts
gateway_end:
_cache_gateway_size = gateway_end-gateway
        .assert gateway_end-gateway < $100, error, "cache gateway installer exceeds a page"
        .assert RUN+gateway_end-gateway <= $f7f0, error, "cache gateway exceeds existing VIC workspace"
