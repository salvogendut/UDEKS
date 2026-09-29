; SPDX-License-Identifier: GPL-3.0-or-later
; One row per lease. No C, callback, service dispatch or task switch while
; worker-flat is mapped. Preserve the caller's I/D flags, return in kernel I/O.
        .setcpu "6502"
        .include "layout.inc"
        .export gateway_start, gateway_end
        .segment "GATEWAY"
gateway_start:
        jmp row_entry
        jmp read_row
        jmp write_row
row_entry:
        php
        sei
        cld
        lda #$00
        sta WORKER
        jsr CORE
        lda #$00
        sta KERNEL
        plp
        rts
setup:
        lda #$00
        sta KERNEL
        clc
        lda OFFSET
        adc #<SHADOW
        sta read_byte+1
        sta write_byte+1
        lda OFFSET+1
        adc #>SHADOW
        sta read_byte+2
        sta write_byte+2
        ldx #$00
        rts
advance:
        clc
        lda read_byte+1
        adc #$08
        sta read_byte+1
        sta write_byte+1
        bcc advanced
        inc read_byte+2
        inc write_byte+2
advanced:
        rts
read_row:
        jsr setup
read_loop:
read_byte:
        lda $ffff
        sta STAGE,x
        jsr advance
        inx
        cpx RAWCOUNT
        bcc read_loop
        jmp worker_return
write_row:
        jsr setup
write_loop:
        lda STAGE,x
write_byte:
        sta $ffff
        jsr advance
        inx
        cpx RAWCOUNT
        bcc write_loop
        ; advance ended one byte-column after the final touched byte. Mark
        ; logical, not physical shadow pages (SHADOW is not page-aligned).
        sec
        lda write_byte+1
        sbc #$08
        sta write_byte+1
        lda write_byte+2
        sbc #$00
        sta write_byte+2
        sec
        lda write_byte+1
        sbc #<SHADOW
        lda write_byte+2
        sbc #>SHADOW
        sta last_page+1
        ldy OFFSET+1
        lda #$01
mark:
        sta DIRTY,y
last_page:
        cpy #$ff
        bcs worker_return
        iny
        bne mark
worker_return:
        lda #$00
        sta WORKER
        rts
gateway_end:
        .assert gateway_start = RUN, error, "cache gateway entry moved"
        .assert gateway_end <= PARAM, error, "cache gateway reaches parameters"
        .assert STAGE+40 <= $f7f0, error, "cache row reaches stack guard"
