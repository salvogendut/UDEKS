; SPDX-License-Identifier: GPL-3.0-or-later
; Transient command veneer for the published UTRQ 0.5 record, not C policy.
        .setcpu "6502"
        .export _udeks_mount_request
        .import popa
        .segment "CODE"
_udeks_mount_request:
        sta $f360                   ; operation, device is on the C stack
        jsr popa
        sta $f367
        ldx #0
        lda $f360
        cmp #17
        bne :+
        inx
:       ldy #0
path:   lda mount_path,y
        sta $f367,x
        inx
        iny
        cpy #4
        bcc path
        stx $f363                   ; count 4 or 5
        ldx #5
header: lda signature,x
        sta $f359,x
        dex
        bpl header
        lda #0
        sta $f362                   ; descriptor
        sta $f366                   ; flags
        sta $f364                   ; result
        sta $f365                   ; errno
        inc $f361                   ; sequence
        lda #1
        sta $f35f                   ; publish request last
        jsr $cf30
        lda $f35f
        cmp #2
        beq success
        lda $f365
        bne returned
        lda #5                      ; malformed/incomplete response: EIO
        bne returned
success: lda #0
returned:
        ldx #0
        rts
        .segment "RODATA"
signature: .byte "UTRQ",0,5
mount_path: .byte "/mnt"
