; SPDX-License-Identifier: GPL-3.0-or-later
; Compact fs_namespace.h implementation for the serialized bank-1 service.
; fs_namespace.c is the independent executable reference. Same cc65 ABI,
; atomic outputs on rejection, no I/O/yield. ptr1..4 are caller-saved scratch.
; Do not name this fs_namespace.s: cl65 uses/deletes that C intermediate.
        .setcpu "6502"
        .macpack longbranch
        .export _udeks_fs_resolve, _udeks_fs_device, _udeks_fs_classify
        .export _udeks_fs_physical, _udeks_fs_consider
        .importzp sp, ptr1, ptr2, ptr3, ptr4
        .import incsp3, incsp4, incsp5
        .segment "BSS"
candidate: .res 19              ; directory, length, folded name[17]
position:  .res 1
limit:     .res 1
kind:      .res 1
        .ifdef UDEKS_NAMESPACE_TEST
        .segment "CODE"
        .else
        .segment "STORAGEHIGH"
        .endif
; Helpers preserve X/Y unless stated. Writes to caller memory only at commit.
lower:
        cmp #$c1
        bcc ascii
        cmp #$db
        bcs ascii
        and #$7f
ascii:  cmp #'A'
        bcc folded
        cmp #'Z'+1
        bcs folded
        ora #$20
folded: rts
name_char:
        cmp #'a'
        bcc digit
        cmp #'z'+1
        bcc valid
digit:  cmp #'0'
        bcc punctuation
        cmp #'9'+1
        bcc valid
punctuation:
        cmp #'.'
        beq valid
        cmp #'-'
        beq valid
        cmp #'_'
        beq valid
        cmp #' '
        beq valid
        sec
        rts
valid:  clc
        rts
invalid:
        .ifdef UDEKS_NAMESPACE_NEGATIVE
        lda #0                   ; qualification only: prove oracle rejects it
        .else
        lda #22
        .endif
        rts
clear_name:
        lda #0
        ldy #17
:       sta candidate+1,y
        dey
        bpl :-
        rts
copy_in:
        ldy #18
:       lda (ptr1),y
        sta candidate,y
        dey
        bpl :-
        rts
copy_out:
        ldy #18
:       lda candidate,y
        sta (ptr2),y
        dey
        bpl :-
        lda #0
        rts
; C=1 for exactly '.' or '..'.
special:
        lda candidate+2
        cmp #'.'
        bne ordinary
        lda candidate+1
        cmp #1
        beq dot
        cmp #2
        bne ordinary
        lda candidate+3
        cmp #'.'
        bne ordinary
dot:    sec
        rts
ordinary:
        clc
        rts
; A=virtual directory (zero means no match).
virtual_dir:
        lda candidate+1
        cmp #3
        bne not_virtual
        lda candidate+2
        cmp #'b'
        bne etc
        lda candidate+3
        cmp #'i'
        bne not_virtual
        lda candidate+4
        cmp #'n'
        bne not_virtual
        lda #1
        rts
etc:    cmp #'e'
        bne mnt
        lda candidate+3
        cmp #'t'
        bne not_virtual
        lda candidate+4
        cmp #'c'
        bne not_virtual
        lda #2
        rts
mnt:    cmp #'m'
        bne not_virtual
        lda candidate+3
        cmp #'n'
        bne not_virtual
        lda candidate+4
        cmp #'t'
        bne not_virtual
        lda #3
        rts
not_virtual:
        lda #0
        rts
; A=RAW(1), BINARY(2), SCRIPT(3) or CONFIG(4); Y clobbered.
suffix_kind:
        ldy candidate+1
        cpy #3
        bcc raw
        lda candidate-1,y
        cmp #'.'
        bne long_suffix
        lda candidate,y
        cmp #'s'
        bne long_suffix
        lda candidate+1,y
        cmp #'h'
        bne long_suffix
        lda #3
        rts
long_suffix:
        cpy #4
        bcc raw
        lda candidate-2,y
        cmp #'.'
        bne raw
        lda candidate-1,y
        cmp #'b'
        bne config
        lda candidate,y
        cmp #'i'
        bne raw
        lda candidate+1,y
        cmp #'n'
        bne raw
        lda #2
        rts
config: cmp #'e'
        bne raw
        lda candidate,y
        cmp #'t'
        bne raw
        lda candidate+1,y
        cmp #'c'
        bne raw
        lda #4
        rts
raw:    lda #1
        rts
; Validate a nonempty logical filename; tail beyond its NUL need not be zero.
bad_candidate:
        lda #22
        rts
validate_candidate:
        lda candidate
        cmp #4
        bcs bad_candidate
        ldy candidate+1
        beq bad_candidate
        cpy #17
        bcs bad_candidate
        lda candidate+2,y
        bne bad_candidate
        jsr special
        bcs bad_candidate
        ldy candidate+1
:       dey
        lda candidate+2,y
        jsr name_char
        bcs bad_candidate
        tya
        bne :-
        rts
_udeks_fs_resolve:
        sta ptr2
        stx ptr2+1
        ldy #0
        lda (sp),y              ; cwd
        sta candidate
        iny
        lda (sp),y              ; bounded path length
        sta limit
        iny
        lda (sp),y
        sta ptr1
        iny
        lda (sp),y
        sta ptr1+1
        jsr resolve
return4:
        ldx #0
        jmp incsp4
resolve:
        lda ptr1
        ora ptr1+1
        jeq invalid
        lda ptr2
        ora ptr2+1
        jeq invalid
        lda candidate
        cmp #4
        jcs invalid
        lda limit
        jeq invalid
        cmp #24
        jcs invalid
        ldy #0
        sty position
        lda (ptr1),y
        cmp #'/'
        bne :+
        sty candidate
:       jsr clear_name
component:
        lda position
        cmp limit
        bcs resolved
        lda candidate+1
        beq skip_slashes
        lda #20                 ; file/anything includes trailing slash
        rts
skip_slashes:
        ldy position
        cpy limit
        bcs resolved
        lda (ptr1),y
        cmp #'/'
        bne collect
        inc position
        bne skip_slashes
collect:
        ldy position
        cpy limit
        bcs component_done
        lda (ptr1),y
        cmp #'/'
        beq component_done
        cmp #$80
        jcs invalid
        jsr lower
        jsr name_char
        jcs invalid
        ldx candidate+1
        cpx #16
        jcs invalid
        sta candidate+2,x
        inc candidate+1
        inc position
        bne collect
component_done:
        jsr special
        bcc named
        lda candidate+1
        cmp #2
        bne :+
        lda #0
        sta candidate
:       jsr clear_name
        jmp component
named:  lda candidate
        bne component
        jsr virtual_dir
        beq component
        sta candidate
        jsr clear_name
        jmp component
resolved:
        lda candidate
        cmp #1
        bne :+
        lda candidate+1
        cmp #14
        jcs invalid
:       lda candidate
        cmp #2
        bne :+
        lda candidate+1
        cmp #13
        jcs invalid
:       jmp copy_out
_udeks_fs_device:
        sta ptr2
        stx ptr2+1
        ldy #1
        lda (sp),y
        sta ptr1
        iny
        lda (sp),y
        sta ptr1+1
        jsr device
return3:
        ldx #0
        jmp incsp3
device:
        lda ptr1
        ora ptr1+1
        jeq invalid
        lda ptr2
        ora ptr2+1
        jeq invalid
        ldy #0
        lda (sp),y
        cmp #4
        jcs invalid
        cmp #3
        bne :+
        iny
:       lda (ptr1),y
        bne :+
        lda #19
        rts
:       cmp #8
        jcc invalid
        cmp #12
        jcs invalid
        ldy #0
        sta (ptr2),y
        tya
        rts
_udeks_fs_classify:
        sta ptr3
        stx ptr3+1
        ldy #0
        lda (sp),y
        sta ptr2
        iny
        lda (sp),y
        sta ptr2+1
        iny
        lda (sp),y
        sta candidate           ; data_volume until checked
        iny
        lda (sp),y
        sta ptr1
        iny
        lda (sp),y
        sta ptr1+1
        jsr classify
        ldx #0
        jmp incsp5
classify:
        lda ptr2
        ora ptr2+1
        jeq invalid
        lda ptr3
        ora ptr3+1
        jeq invalid
        jsr classify_core
        bne :+
        jsr copy_out
        ldy #0
        lda kind
        sta (ptr3),y
        tya
:       rts
; Private scratch only; CONSIDER calls this too. ptr3/ptr4 are preserved.
classify_core:
        lda ptr1
        ora ptr1+1
        jeq invalid
        lda candidate
        cmp #2
        jcs invalid
        lda candidate
        beq :+
        lda #3
        sta candidate
:       jsr clear_name
        lda #1
        sta kind
        ldy #0
classify_char:
        lda (ptr1),y
        cmp #$a0
        beq padding
        jsr lower
        jsr name_char
        jcs invalid
        sta candidate+2,y
        inc candidate+1
        iny
        cpy #16
        bcc classify_char
        bcs name_done
padding:
        lda (ptr1),y
        cmp #$a0
        jne invalid
        iny
        cpy #16
        bcc padding
name_done:
        lda candidate+1
        jeq invalid
        lda candidate
        bne classified
        jsr suffix_kind
        sta kind
        cmp #1
        beq classified
        ldx #4
        cmp #3
        bne :+
        dex
:       stx position
        lda candidate+1
        sec
        sbc position
        sta candidate+1
        ldy #1
        lda kind
        cmp #4
        bne :+
        iny
:       sty candidate
        ldy candidate+1
        lda #0
:       sta candidate+2,y
        iny
        cpy #17
        bcc :-
classified:
        lda candidate+1
        jeq invalid
        jsr special
        jcs invalid
        lda candidate
        bne classify_ok
        jsr virtual_dir
        beq classify_ok
collision:
        lda #17
        rts
classify_ok:
        lda #0
        rts
_udeks_fs_consider:
        sta ptr3
        stx ptr3+1
        ldy #2
        lda (sp),y
        sta ptr1
        sta ptr4
        iny
        lda (sp),y
        sta ptr1+1
        sta ptr4+1
        jsr consider
        jmp return4
consider:
        lda ptr1
        ora ptr1+1
        jeq invalid
        lda ptr3
        ora ptr3+1
        jeq invalid
        ldy #0
        lda (ptr3),y
        cmp #5
        jcs invalid
        jsr copy_in
        jsr validate_candidate
        bne consider_done
        lda candidate
        cmp #3
        lda #0
        adc #0                  ; C=1 iff MNT (validated dir<=3)
        sta candidate
        ldy #0
        lda (sp),y
        sta ptr1
        iny
        lda (sp),y
        sta ptr1+1
        jsr classify_core
        bne consider_done
        lda candidate+1
        clc
        adc #2
        tax
        ldy #0
:       lda candidate,y
        cmp (ptr4),y
        bne no_match
        iny
        dex
        bne :-
        ldy #0
        lda (ptr3),y
        bne collision
        lda kind
        sta (ptr3),y
        tya
consider_done:
        rts
no_match:
        lda #2
        rts
_udeks_fs_physical:
        sta ptr2
        stx ptr2+1
        ldy #0
        lda (sp),y
        sta kind
        iny
        lda (sp),y
        sta ptr1
        iny
        lda (sp),y
        sta ptr1+1
        jsr physical
        jmp return3
physical:
        lda ptr1
        ora ptr1+1
        jeq invalid
        lda ptr2
        ora ptr2+1
        jeq invalid
        jsr copy_in
        jsr validate_candidate
        jne physical_done
        lda kind
        jeq bad_physical
        cmp #5
        jcs bad_physical
        tax
        lda #0
        sta position            ; suffix length
        cpx #1
        bne mapped_kind
        lda candidate
        beq raw_root
        cmp #3
        jne bad_physical
        beq emit
raw_root:
        jsr virtual_dir
        jne collision
        jsr suffix_kind
        cmp #1
        jne no_match
        beq emit
mapped_kind:
        lda candidate
        ldy #1
        cpx #4
        bne :+
        iny
:       sty position
        cmp position
        bne bad_physical
        ldy #4
        cpx #3
        bne :+
        dey
:       sty position
        tya
        clc
        adc candidate+1
        cmp #17
        bcs bad_physical
emit:
        clc
        lda ptr1
        adc #2
        sta ptr1
        bcc :+
        inc ptr1+1
:       ldy #0
emit_name:
        lda (ptr1),y
        cmp #'a'
        bcc :+
        cmp #'z'+1
        bcs :+
        and #$df
:       sta (ptr2),y
        iny
        cpy candidate+1
        bcc emit_name
        lda position
        beq fill
        ldx kind
        lda suffix_offsets,x
        tax
:       lda suffixes,x
        beq fill
        sta (ptr2),y
        inx
        iny
        bne :-
fill:   cpy #16
        bcs physical_ok
        lda #$a0
:       sta (ptr2),y
        iny
        cpy #16
        bcc :-
physical_ok:
        lda #0
physical_done:
        rts
bad_physical:
        lda #22
        rts
suffix_offsets:
        .byte 0,0,0,5,9
suffixes:
        .byte ".BIN",0,".SH",0,".ETC",0
