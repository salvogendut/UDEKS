; SPDX-License-Identifier: GPL-3.0-or-later
; Time-service policy, shared by the compatibility image and disk module.
; A=hour, X=minute, Y=second; A=0 on success, 1 for invalid arguments.
clock_set_runtime:
        cmp #$18
        bcs clock_set_invalid
        cpx #$3c
        bcs clock_set_invalid
        cpy #$3c
        bcs clock_set_invalid
        sta $f208
        stx $f209
        sty $f20a
        lda $dc0f
        and #$7f
        sta $dc0f
        lda $f208
        beq clock_set_midnight
        cmp #$0c
        beq clock_set_noon
        bcc clock_set_am
        sec
        sbc #$0c
        jsr clock_binary_bcd
        ora #$80
        bne clock_set_hour_ready
clock_set_midnight:
        ; The 6526 toggles PM when $12 is written. $00/$80 are the documented
        ; safe encodings for setting midnight/noon without that anomaly.
        lda #$00
        jmp clock_set_hour_ready
clock_set_noon:
        lda #$80
        bne clock_set_hour_ready
clock_set_am:
        jsr clock_binary_bcd
clock_set_hour_ready:
        sta $dc0b
        lda $f209
        jsr clock_binary_bcd
        sta $dc0a
        lda $f20a
        jsr clock_binary_bcd
        sta $dc09
        lda #$00
        sta $f20b
        sta $dc08
        inc $f20c
        jsr _udeks_time_sync_ti
        lda #$00
        rts
clock_set_invalid:
        lda #$01
        rts

clock_binary_bcd:
        ldx #$00
clock_binary_bcd_digit:
        cmp #$0a
        bcc clock_binary_bcd_ready
        sbc #$0a
        inx
        bne clock_binary_bcd_digit
clock_binary_bcd_ready:
        sta tmp1
        txa
        asl a
        asl a
        asl a
        asl a
        ora tmp1
        rts

        ; Rebuild BASIC's high/middle/low TI bytes from the published
        ; HH:MM:SS.t value. CIA TOD has tenth-second resolution, hence +6.
_udeks_time_sync_ti:
        lda $f20b
        cmp $f20c
        beq clock_sync_done
        sta $f20c
        lda #$00
        sta $a0
        sta $a1
        sta $a2
        ldy $f208
        ldx #$4b
        jsr clock_add_loop
        ldy $f209
        ldx #$0e
        jsr clock_add_loop
        ldy $f20a
        ldx #$00
        jsr clock_add_loop
        ldy $f20b
clock_add_tenth:
        beq clock_sync_done
        clc
        lda $a2
        adc #$06
        sta $a2
        bcc :+
        inc $a1
        bne :+
        inc $a0
:
        dey
        bne clock_add_tenth
clock_sync_done:
        rts

        ; Add Y copies of the constant selected by X. The high byte is $03
        ; only for hours; minutes and seconds cannot carry beyond their range.
clock_add_loop:
        sty tmp1
        tya
        beq clock_add_done
clock_add_again:
        cpx #$4b
        bne :+
        lda #$c0
        bne clock_add_value
:
        cpx #$0e
        bne :+
        lda #$10
        bne clock_add_value
:
        lda #$3c
clock_add_value:
        clc
        adc $a2
        sta $a2
        txa
        adc $a1
        sta $a1
        lda #$00
        adc $a0
        sta $a0
        ; Hour contributions need the additional fixed high-byte value.
        cpx #$4b
        bne :+
        clc
        lda $a0
        adc #$03
        sta $a0
:
        dec tmp1
        beq clock_add_done
        bne clock_add_again
clock_add_done:
        rts
