        .setcpu "6502"
COPY_SOURCE      = $f8
COPY_DESTINATION = $fa
COPY_LENGTH      = $fc
SCATTER_MANIFEST = $ab2d
SCATTER_TEMP     = $1200
KERNEL_ENTRY     = $2000

        .segment "CODE"
gather_scatter:
        lda #<(SCATTER_MANIFEST+5)
        sta COPY_SOURCE
        lda #>(SCATTER_MANIFEST+5)
        sta COPY_SOURCE+1
        lda #<SCATTER_TEMP
        sta COPY_DESTINATION
        lda #>SCATTER_TEMP
        sta COPY_DESTINATION+1
        ldx SCATTER_MANIFEST+4
        beq gather_done
gather_entry:
        ldy #$00
        lda (COPY_SOURCE),y
        sta gather_load+1
        iny
        lda (COPY_SOURCE),y
        sta gather_load+2
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
        bcc gather_copy
        inc COPY_SOURCE+1
gather_copy:
        ldy #$00
gather_byte:
        lda COPY_LENGTH
        ora COPY_LENGTH+1
        beq gather_next
gather_load:
        lda $ffff,y
        sta (COPY_DESTINATION),y
        inc gather_load+1
        bne gather_src_ok
        inc gather_load+2
gather_src_ok:
        inc COPY_DESTINATION
        bne gather_dst_ok
        inc COPY_DESTINATION+1
gather_dst_ok:
        lda COPY_LENGTH
        bne gather_len_ok
        dec COPY_LENGTH+1
gather_len_ok:
        dec COPY_LENGTH
        jmp gather_byte
gather_next:
        dex
        bne gather_entry
gather_done:
        rts
gather_end:

scheduler_install:
        lda #$12
        sta install_source+2
        lda #$1c
        sta install_dest+2
        ldx #$04
install_page:
        ldy #$00
install_byte:
install_source:
        lda $1200,y
install_dest:
        sta $1c00,y
        iny
        bne install_byte
        inc install_source+2
        inc install_dest+2
        dex
        bne install_page
        jmp KERNEL_ENTRY
install_end:
        .out .sprintf("gather=%d install=%d total=%d", gather_end-gather_scatter, install_end-scheduler_install, install_end-gather_scatter)
