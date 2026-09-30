; SPDX-License-Identifier: GPL-3.0-or-later
; Reference only: stock C128 KERNAL reads ONE on a non-boot test disk.
; Never linked into UDEKS. Raw-load at $2800; result $3100..$32ff.
        .setcpu "6502"
        .segment "CODE"
entry:
        lda #0
        sta $ff00
        sta $d030
        cli
        ldx #0
clear:  sta $3100,x
        inx
        bne clear
        jsr $ff68              ; SETBNK: file and filename bank zero
        lda #3
        ldx #<filename
        ldy #>filename
        jsr $ffbd              ; SETNAM
        lda #2
        ldx #8
        ldy #2
        jsr $ffba              ; SETLFS
        jsr $ffc0              ; OPEN
        bcs failed
        ldx #2
        jsr $ffc6              ; CHKIN
        bcs failed
read:
        jsr $ffcf              ; CHRIN
        ldx $3104
        sta $3200,x
        inc $3104
        bne status
        inc $3105
status: jsr $ffb7              ; READST
        sta $3102
        bne finish
        lda $3105
        beq read
        lda #$ff               ; hard bound: no more than 256 bytes
        sta $3102
finish: jsr $ffcc              ; CLRCHN
        lda #2
        jsr $ffc3              ; CLOSE
        lda #2
        sta $3100
stop:   jmp stop
failed: sta $3101
        lda #$80
        sta $3100
        jmp stop
filename: .byte "ONE"
        .segment "BSS"
unused: .res 1
