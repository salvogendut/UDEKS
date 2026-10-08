; SPDX-License-Identifier: GPL-3.0-or-later
; Compact exact-name DOS backend. cbm_mutate.c is the independent oracle.
; No resident ZP, no DOS retry, no wildcard, no CLOSE 15.
        .setcpu "6502"
        .macpack longbranch
        .export _udeks_cbm_mutate
        .importzp sp, ptr1, ptr2
        .import incsp4
        .import _udeks_iec_begin_command, _udeks_iec_command
        .import _udeks_iec_open_status, _udeks_iec_read_byte
        .import _udeks_iec_untalk, _udeks_iec_unlisten, _udeks_iec_finish
        .import _udeks_iec_filename, _udeks_iec_filename_length
        .ifdef UDEKS_IEC_ASYNC
        .export _udeks_cbm_mutate_poll
        .export _udeks_cbm_mutate_abort := _udeks_iec_finish
        .export _udeks_cbm_write_status
        .import _udeks_iec_poll_status
        .import _udeks_cbm_write_dos_error
        .endif
        .segment "BSS"
source: .res 2
dest:   .res 2
op:     .res 1
unit:   .res 1
n:      .res 1
m:      .res 1
length: .res 1
; Once the command is sent, the pointer/name scratch is no longer live.
field = source
digits = source+1
number = dest
code = dest+1
count = unit
limit = n

        .ifdef UDEKS_MUTATION_TEST
        .segment "CODE"
        .else
        .segment "STORAGEHIGH"
        .endif
_udeks_cbm_mutate:
        sta dest
        sta ptr2
        stx dest+1
        stx ptr2+1
        ldy #0
        lda (sp),y
        sta source
        sta ptr1
        iny
        lda (sp),y
        sta source+1
        sta ptr1+1
        iny
        lda (sp),y
        sta op
        iny
        lda (sp),y
        sta unit
        jsr incsp4
        lda unit
        sec
        sbc #8
        cmp #4
        bcs invalid
        lda op
        beq invalid
        cmp #4
        bcs invalid
        jsr name_length
        beq invalid
        sta n
        lda op
        cmp #3
        bne pair
        lda dest
        ora dest+1
        bne invalid
        beq begin
pair:   lda dest
        sta ptr1
        lda dest+1
        sta ptr1+1
        jsr name_length
        beq invalid
        sta m
        cmp n
        bne begin
        lda source
        sta ptr1
        lda source+1
        sta ptr1+1
        ldy #0
same:   lda (ptr1),y
        cmp (ptr2),y
        bne begin
        iny
        cpy n
        bne same
        lda #17
        bne ret
invalid:
        lda #22
ret:    ldx #0
        rts
begin:  lda unit
        jsr _udeks_iec_begin_command
        cmp #0
        beq build
        cmp #4
        bne io_error
        lda #16
        bne ret
io_error:
        lda #5
        bne ret
build:  ldx op
        lda commands-1,x
        sta _udeks_iec_filename
        lda #'0'
        sta _udeks_iec_filename+1
        lda #':'
        sta _udeks_iec_filename+2
        ldx #3
        lda op
        cmp #3
        beq append_source
        lda dest
        sta ptr1
        lda dest+1
        sta ptr1+1
        lda m
        jsr append
        lda #'='
        sta _udeks_iec_filename,x
        inx
        lda op
        cmp #2
        bne append_source
        lda #'0'
        sta _udeks_iec_filename,x
        inx
        lda #':'
        sta _udeks_iec_filename,x
        inx
append_source:
        lda source
        sta ptr1
        lda source+1
        sta ptr1+1
        lda n
        jsr append
        stx _udeks_iec_filename_length
        jsr _udeks_iec_command
        cmp #0
        jne command_failed
        .ifdef UDEKS_IEC_ASYNC
        lda #$ff
        sta n
        sta m
        .endif
        jmp status
        .ifndef UDEKS_MUTATION_TEST
        .segment "CODE"
        .endif
command_failed:
        pha
        jsr _udeks_iec_unlisten
        pla
        cmp #3
        bne command_error
        lda #19
        jne finish
command_error:
        lda #5
        jmp finish
        .ifndef UDEKS_MUTATION_TEST
        .segment "IECCODE"
        .endif
finish: pha
        jsr _udeks_iec_finish
        pla
        ldx #0
        rts
append: sta length
        ldy #0
loop:   lda (ptr1),y
        sta _udeks_iec_filename,x
        inx
        iny
        cpy length
        bne loop
        rts

; Exactly 16 padded bytes, with no gaps, edge spaces, '.' or '..'.
        .ifndef UDEKS_MUTATION_TEST
        .segment "STORAGECODE"
        .endif
name_length:
        lda ptr1
        ora ptr1+1
        jeq bad_name
        lda #16
        sta length
        ldy #0
next:   lda (ptr1),y
        cmp #$a0
        bne char
        cpy length
        bcs advance
        sty length
        bcc advance
char:   ldx length
        cpx #16
        bne bad_name
        cmp #' '
        beq advance
        cmp #'.'
        beq advance
        cmp #'-'
        beq advance
        cmp #'_'
        beq advance
        cmp #'0'
        bcc bad_name
        cmp #'9'+1
        bcc advance
        cmp #$80
        bcc ascii
        cmp #$c1
        bcc bad_name
        cmp #$db
        bcs bad_name
        bcc advance
ascii:
        and #$df
        cmp #'A'
        bcc bad_name
        cmp #'Z'+1
        bcs bad_name
advance:
        iny
        cpy #16
        bne next
        ldy length
        beq bad_name
        dey
        lda (ptr1),y
        cmp #' '
        beq bad_name
        ldy #0
        lda (ptr1),y
        cmp #' '
        beq bad_name
        cmp #'.'
        bne good_name
        lda length
        cmp #1
        beq bad_name
        cmp #2
        bne good_name
        iny
        lda (ptr1),y
        cmp #'.'
        beq bad_name
good_name:
        lda length
        rts
bad_name:
        lda #0
        rts

        .ifndef UDEKS_MUTATION_TEST
        .segment "STORAGEHIGH"
        .endif
        .ifndef UDEKS_MUTATION_TEST
        .segment "IECCODE"
        .endif
status:
        .ifdef UDEKS_IEC_ASYNC
_udeks_cbm_mutate_poll:
        jsr _udeks_iec_poll_status
        cmp #5
        jne status_opened
        lda n
        bne :+
        dec m
:       dec n
        lda n
        ora m
        beq expired
        lda #11
        ldx #0
        rts
expired:
        lda #5
        jmp finish                ; release bus; no retransmission
        .else
        jsr _udeks_iec_open_status
        .endif
        .ifndef UDEKS_MUTATION_TEST
        .segment "CODE"
        .endif
status_opened:
        cmp #0
        jne bad_parse
parser_init:
        lda #0
        sta field
        sta digits
        sta number
        lda #64
        sta limit
        jmp read
        .ifndef UDEKS_MUTATION_TEST
        .segment "STORAGEHIGH"
        .endif
read:   jsr _udeks_iec_read_byte
        cpx #2
        bcs bad_parse
        cpx #1
        beq end_status
        ldx field
        cpx #1
        beq text_field
        cmp #','
        beq comma
        cmp #'0'
        bcc bad_parse
        cmp #'9'+1
        bcs bad_parse
        ldx digits
        cpx #2
        bcs bad_parse
        adc #$d0                  ; CPX #2 left C=0; ASCII digit minus '0'
        pha
        lda number
        asl a
        sta m
        asl a
        asl a
        adc m
        sta number
        pla
        adc number
        sta number
        inc digits
        bne again
bad_parse:
        jmp bad_status
text_field:
        cmp #','
        beq text_end
        cmp #32
        bcc bad_parse
        inc digits
        bne again
text_end:
        lda digits
        beq bad_parse
        bne new_field
comma:  lda digits
        cmp #2
        bne bad_parse
        cpx #3
        beq bad_parse
        lda number
        dex                       ; field is 0 or 2
        bpl track
        sta code
        jmp new_field
track:  sta count
new_field:
        inc field
        lda #0
        sta number
        sta digits
again:  dec limit
        jne read
        jmp bad_status
end_status:
        cmp #13
        bne bad_status
        lda field
        cmp #3
        bne bad_status
        lda digits
        cmp #2
        bne bad_status
        lda code
        beq success_code
        cmp #1
        beq scratched
        jsr dos_errno
        jmp done
        .ifndef UDEKS_MUTATION_TEST
        .segment "IECCODE"
        .endif
dos_errno:
        cmp #0
        beq errno_return
        ldx #6
errno:  cmp codes,x
        beq mapped
        dex
        bpl errno
        lda #5
        bne errno_return
mapped: lda errors,x
errno_return:
        ldx #0
        rts
errors: .byte 30,16,2,17,16,28,19
        .ifndef UDEKS_MUTATION_TEST
        .segment "CODE"
        .endif
commands: .byte 'R','C','S'
        .ifndef UDEKS_MUTATION_TEST
        .segment "IECCODE"
        .endif
codes:  .byte 26,60,62,63,70,72,74
        .ifndef UDEKS_MUTATION_TEST
        .segment "STORAGEHIGH"
        .endif
success_code:
        lda op
        cmp #3
        beq bad_status
        lda count
        ora number
        beq done
        bne bad_status
scratched:
        lda op
        cmp #3
        bne bad_status
        lda number
        bne bad_status
        lda count
        cmp #1
        beq success
        cmp #0
        bne bad_status
        lda #2
        bne done
success:
        lda #0
        beq done
bad_status:
        lda #5
done:   pha
        jsr _udeks_iec_untalk
        tax
        pla
        cpx #0
        beq :+
        lda #5
:       jmp finish

        .ifdef UDEKS_IEC_ASYNC
        .ifndef UDEKS_MUTATION_TEST
        .segment "STORAGECODE"
        .endif
; Writer's existing bounded parser, sharing only errno mapping/scratch.
; Keep the weaker legacy grammar unchanged; mutations use full grammar above.
_udeks_cbm_write_status:
        lda #0
        sta _udeks_cbm_write_dos_error
        sta code
        sta digits
        sta m
        jsr _udeks_iec_open_status
        cmp #0
        bne write_bad
write_read:
        jsr _udeks_iec_read_byte
        cpx #2
        bcs write_bad
        sta number
        stx field
        ldx digits
        cpx #2
        bcs write_comma
        cmp #'0'
        bcc write_mark_bad
        cmp #'9'+1
        bcs write_mark_bad
        sec
        sbc #'0'
        pha
        lda code
        asl a
        sta count
        asl a
        asl a
        adc count
        sta code
        pla
        clc
        adc code
        sta code
        jmp write_eoi
write_comma:
        bne write_eoi
        cmp #','
        beq write_eoi
write_mark_bad:
        inc m
write_eoi:
        lda field
        bne write_end
        inc digits
        lda digits
        cmp #64
        bcc write_read
write_bad:
        lda #1
        sta m
        bne write_done
write_end:
        lda number
        cmp #13
        bne write_bad
        lda digits
        cmp #3
        bcc write_bad
write_done:
        jsr _udeks_iec_untalk
        ora m
        bne write_error
        lda code
        sta _udeks_cbm_write_dos_error
        jmp dos_errno
write_error:
        lda #5
        ldx #0
        rts
        .endif
