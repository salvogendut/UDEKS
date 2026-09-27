; SPDX-License-Identifier: GPL-3.0-or-later
;
; Boot-only scatter gather for the scheduler delivery. Stage 1 calls the fixed
; $2003 vector before crt0; the routine gathers the scheduler chunks listed in
; the manifest into the temporary application slot at $1200-$15FF, validates
; the manifest magic and the 16-bit image checksum, and returns A=0 on
; success. It uses no BSS or cc65 runtime state; $F8-$FD are stage 1's retired
; copy scratch.

        .setcpu "6502"
        .export _boot_delivery_gather

COPY_SOURCE      = $f8
COPY_DESTINATION = $fa
COPY_LENGTH      = $fc
SCATTER_MANIFEST = $acd9
SCATTER_TEMP     = $1200
BOOT_CHAIN       = $f050
BOOT_CHAIN_STATE = BOOT_CHAIN + 12
BOOT_CHAIN_FAILURE = BOOT_CHAIN + 13

        .segment "BOOTDELIVERY"
_boot_delivery_gather:
        lda SCATTER_MANIFEST+0
        cmp #'U'
        bne delivery_magic_fail
        lda SCATTER_MANIFEST+1
        cmp #'S'
        bne delivery_magic_fail
        lda SCATTER_MANIFEST+2
        cmp #'C'
        bne delivery_magic_fail
        lda SCATTER_MANIFEST+3
        cmp #'T'
        bne delivery_magic_fail
        jmp delivery_body
delivery_magic_fail:
        lda #$01
        jmp delivery_fail

delivery_body:
        lda #<SCATTER_TEMP
        sta COPY_DESTINATION
        lda #>SCATTER_TEMP
        sta COPY_DESTINATION+1
        ldx #$04
        lda #$00
delivery_zero_page:
        ldy #$00
delivery_zero_byte:
        sta (COPY_DESTINATION),y
        iny
        bne delivery_zero_byte
        inc COPY_DESTINATION+1
        dex
        bne delivery_zero_page

        lda #<(SCATTER_MANIFEST+7)
        sta COPY_SOURCE
        lda #>(SCATTER_MANIFEST+7)
        sta COPY_SOURCE+1
        lda #<SCATTER_TEMP
        sta COPY_DESTINATION
        lda #>SCATTER_TEMP
        sta COPY_DESTINATION+1
        ldx SCATTER_MANIFEST+4
        bne delivery_entry
        jmp delivery_verify

delivery_entry:
        ldy #$00
        lda (COPY_SOURCE),y
        sta delivery_load+1
        iny
        lda (COPY_SOURCE),y
        sta delivery_load+2
        iny
        lda (COPY_SOURCE),y
        sta COPY_LENGTH
        iny
        lda (COPY_SOURCE),y
        sta COPY_LENGTH+1
        clc
        lda COPY_SOURCE
        adc #$04
        sta COPY_SOURCE
        bcc delivery_copy
        inc COPY_SOURCE+1
delivery_copy:
        ldy #$00
delivery_byte:
        lda COPY_LENGTH
        ora COPY_LENGTH+1
        beq delivery_next
delivery_load:
        lda $ffff,y
        sta (COPY_DESTINATION),y
        inc delivery_load+1
        bne delivery_src_ok
        inc delivery_load+2
delivery_src_ok:
        inc COPY_DESTINATION
        bne delivery_dst_ok
        inc COPY_DESTINATION+1
delivery_dst_ok:
        lda COPY_LENGTH
        bne delivery_len_ok
        dec COPY_LENGTH+1
delivery_len_ok:
        dec COPY_LENGTH
        jmp delivery_byte
delivery_next:
        dex
        bne delivery_entry

delivery_verify:
        lda #$00
        sta delivery_sum
        sta delivery_sum+1
        lda #<SCATTER_TEMP
        sta COPY_SOURCE
        lda #>SCATTER_TEMP
        sta COPY_SOURCE+1
        ldx #$04
delivery_sum_page:
        ldy #$00
delivery_sum_byte:
        clc
        lda delivery_sum
        adc (COPY_SOURCE),y
        sta delivery_sum
        bcc delivery_sum_ok
        inc delivery_sum+1
delivery_sum_ok:
        iny
        bne delivery_sum_byte
        inc COPY_SOURCE+1
        dex
        bne delivery_sum_page
        lda delivery_sum
        cmp SCATTER_MANIFEST+5
        bne delivery_bad_sum
        lda delivery_sum+1
        cmp SCATTER_MANIFEST+6
        bne delivery_bad_sum
        lda #$00
        rts

delivery_bad_sum:
        lda #$02
delivery_fail:
        sta BOOT_CHAIN_FAILURE
        lda #$81
        sta BOOT_CHAIN_STATE
        lda #$01
        rts

delivery_sum:
        .byte $00, $00
