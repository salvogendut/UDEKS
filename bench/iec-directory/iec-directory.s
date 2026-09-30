; SPDX-License-Identifier: GPL-3.0-or-later
; Standalone native-IEC qualification PRG, not part of the UDEKS kernel.
; VICE monitor raw-loads this at $2800, with a true-drive D64 on device 8.
; Result $3100: state, open, last read, close, byte-count low/high, then the
; first 256 directory bytes at $3200. State 2 is complete, $80 is failure.
        .setcpu "6502"
        .import _udeks_iec_open_directory
        .import _udeks_iec_open_file
        .import _udeks_iec_filename
        .import _udeks_iec_filename_length
        .import _udeks_iec_read_byte
        .import _udeks_iec_close
        .import _udeks_iec_probe_phase
        .import _udeks_iec_probe_subphase
        .import _udeks_iec_probe_bus
        .import _udeks_iec_probe_lines
        .import _udeks_iec_probe_bits

RESULT  = $3100

        .segment "CODE"
entry:
        ; raw-load uses all-RAM; restore the C128 native ROM/I/O profile so
        ; CIA2 and the ordinary machine IRQ continue to work during the test.
        lda #$00
        sta $ff00
        tax
@clear_bss:
        sta $3000,x
        inx
        bne @clear_bss
        lda $d030
        ora #$01              ; qualify save/restore from 2 MHz
        sta $d030
        sta RESULT+10
        lda $dd00
        and #$03
        sta RESULT+14
        lda #$00
        sta RESULT
        sta RESULT+1
        sta RESULT+2
        sta RESULT+3
        sta RESULT+4
        sta RESULT+5
        lda #$08
        ldx RESULT+16             ; 0=directory, 1=32 bytes, 2=short EOI, 3=512 bytes
        beq @directory
        cpx #$02
        beq @short_name
        ldx #$07
@copy_name:
        lda test_name,x
        sta _udeks_iec_filename,x
        dex
        bpl @copy_name
        lda #$08
        sta _udeks_iec_filename_length
        jmp @open_file
@short_name:
        ldx #$04
@copy_short_name:
        lda short_name,x
        sta _udeks_iec_filename,x
        dex
        bpl @copy_short_name
        lda #$05
        sta _udeks_iec_filename_length
@open_file:
        lda #$08
        jsr _udeks_iec_open_file
        jmp @opened
@directory:
        jsr _udeks_iec_open_directory
@opened:
        sta RESULT+1
        lda _udeks_iec_probe_phase
        sta RESULT+6
        lda _udeks_iec_probe_subphase
        sta RESULT+7
        lda _udeks_iec_probe_bus
        sta RESULT+8
        lda _udeks_iec_probe_lines
        sta RESULT+9
        lda $d030
        sta RESULT+11
        lda RESULT+1
        beq read_next
        jmp failed
read_next:
        jsr _udeks_iec_read_byte
        stx RESULT+2
        cpx #$02
        bcs read_failed
write_byte:
        sta $3200
        inc write_byte+1
        inc RESULT+4
        bne @counted
        inc write_byte+2
        inc RESULT+5
@counted:
        cpx #$01
        beq close
        lda RESULT+16
        beq @directory_limit
        cmp #$02
        beq read_next
        cmp #$03
        beq @long_limit
        lda RESULT+4
        cmp #$20                  ; named-file sample is a bounded 32 bytes
        beq close
        jmp read_next
@long_limit:
        lda RESULT+5
        cmp #$02                  ; two pages cross a disk-sector boundary
        beq close
        jmp read_next
@directory_limit:
        lda RESULT+5
        cmp #$01
        bne read_next
close:
        jsr _udeks_iec_close
        sta RESULT+3
        lda $d030
        sta RESULT+12
        lda $dd00
        and #$38
        sta RESULT+13
        lda $dd00
        and #$03
        sta RESULT+15
        lda RESULT+3
        bne failed
        lda #$02
        sta RESULT
        jmp halt
read_failed:
        lda _udeks_iec_probe_subphase
        sta RESULT+7
        lda _udeks_iec_probe_bits
        sta RESULT+17
        lda _udeks_iec_probe_bus
        sta RESULT+8
        lda _udeks_iec_probe_lines
        sta RESULT+9
        jsr _udeks_iec_close
failed:
        lda $d030
        sta RESULT+12
        lda $dd00
        and #$38
        sta RESULT+13
        lda $dd00
        and #$03
        sta RESULT+15
        lda #$80
        sta RESULT
halt:
        jmp halt

test_name:
        .byte $d4,$c5,$d3,$d4,$d0,$d2,$cf,$c7 ; TESTPROG on the disk
short_name:
        .byte $c8,$c5,$cc,$cc,$cf               ; HELLO on the disk
