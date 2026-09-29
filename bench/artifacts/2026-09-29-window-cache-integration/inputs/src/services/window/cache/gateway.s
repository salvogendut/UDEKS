; SPDX-License-Identifier: GPL-3.0-or-later
; One shared lease for the C command AND its row copier. Never switch to C
; while the private software-stack bank is hidden by a row read/write.
        .setcpu "6502"
        .include "layout.inc"
        .export gateway_start, gateway_end
        .segment "GATEWAY"
gateway_start:
        jmp command_entry
        jmp read_row
        jmp write_row
command_entry:
        cld
        ldx #ZP_BYTES-1
save_zp:
        lda ZP_FIRST,x
        pha
        dex
        bpl save_zp
        sta WORKER
        lda #<STACK_TOP
        sta ZP_FIRST
        lda #>STACK_TOP
        sta ZP_FIRST+1
        lda OP
        jsr DISPATCH
        sta RESULT
        lda ZP_FIRST
        sta RETURN_SP
        lda ZP_FIRST+1
        sta RETURN_SP+1
        sta KERNEL
        ldx #$00
restore_zp:
        pla
        sta ZP_FIRST,x
        inx
        cpx #ZP_BYTES
        bcc restore_zp
        lda RESULT
        ldx #$00
        rts
setup:
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
        ; Logical last offset = OFFSET + (RAWCOUNT-1)*8. Two carries
        ; handle a 40-byte row crossing up to two logical page boundaries.
        dex
        txa
        asl a
        asl a
        asl a
        ldy OFFSET+1
        bcc :+
        iny
:
        clc
        adc OFFSET
        bcc :+
        iny
:
        sty last_page+1
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
        sta WORKER
        rts
gateway_end:
        .assert gateway_start = RUN, error, "combined gateway moved"
        .assert gateway_end <= PARAM, error, "gateway reaches parameters"
        .assert STAGE+40 <= $f7f0, error, "row reaches stack guard"
