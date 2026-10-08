; SPDX-License-Identifier: GPL-3.0-or-later
; UTRQ 0.18 client. Earlier kernels reject this version. Internal op bit 7
; selects wire flag 1 (poll), never a second DOS submission.
        .setcpu "6502"
        .export _udeks_mutation_request
        .import popa, _udeks_errno
        .segment "CODE"
_udeks_mutation_request:
        sta $f363
        jsr popa
        sta $f362
        jsr popa
        pha
        and #$7f
        sta $f360
        ldx #5
copy:   lda signature,x
        sta $f359,x
        dex
        bpl copy
        lda #0
        sta $f364
        sta $f365
        pla
        asl a
        lda #0
        rol a
        sta $f366
        inc $f361
        lda #1
        sta $f35f
        jsr $cf30
        lda $f35f
        cmp #2
        bne error
        lda $f365
        bne error
        lda $f364
        cmp #2
        bcs malformed
        pha
        lda #0
        sta _udeks_errno
        tax
        pla
        rts
malformed:
        lda #5
        bne failed
error:  lda $f365
        beq malformed
failed: sta _udeks_errno
        lda #$ff
        ldx #0
        rts
        .segment "RODATA"
signature: .byte "UTRQ",0,18
