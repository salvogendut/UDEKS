; SPDX-License-Identifier: GPL-3.0-or-later
        .export _udeks_graphics_record = $f359
        .setcpu "6502"
        .export _udeks_banked_call, _udeks_banked_read, _udeks_banked_write
        .export _udeks_banked_graphics_exec
        .export _udeks_banked_graphics_control_stop
        .import _udeks_banked_graphics_launch
        .import _udeks_banked_graphics_names, _udeks_banked_legacy_names
        .import _udeks_banked_graphics_installed, _udeks_banked_graphics_stop
        .import _udeks_shell_stop_app
        .importzp ptr1
        .segment "GRAPHICSHELP"
_udeks_banked_call:
        jmp $f91c
_udeks_banked_read:
        ldy #$20
        bne transfer
_udeks_banked_write:
        ldy #$21
transfer:
        sta $f367
        stx $f368
        tya
        jmp $f91c
legacy_not_ready:
        lda #1
        ldx #0
        rts

; Name is a resident-session pointer, never a foreign task pointer. Build the
; bounded, padded loader request before borrowing the worker-bank service.
        .segment "CODE"
_udeks_banked_graphics_exec:
        sta ptr1
        stx ptr1+1
        ldy #0
name_copy:
        lda (ptr1),y
        beq name_end
        cpy #16
        bcs name_bad
        sta $f368,y
        iny
        bne name_copy
name_end:
        sty $f367
name_pad:
        cpy #16
        bcs name_ready
        sta $f368,y
        iny
        bne name_pad
name_ready:
        lda #17
        sta $f363
        jmp _udeks_banked_graphics_launch
name_bad:
        lda #5
        ldx #0
        rts

; Frozen named CONTROL requests may not stop an unrelated generic instance.
; The foreground/desktop paths still stop by the registered instance slot.
_udeks_banked_graphics_control_stop:
        cmp #4
        bcc :+
        jmp legacy_native
:
        jmp _udeks_shell_stop_app
        .segment "MODULECODE"
legacy_native:
        lsr a
        lsr a
        lsr a
        tax
        lda _udeks_banked_graphics_installed
        bne legacy_choose
        lda #1
        ldx #0
        rts
legacy_choose:
        txa
        beq legacy_first
        ldx #16
        lda #6
legacy_first:
        tay
        jmp legacy_compare
        .segment "GRAPHICSCODE"
legacy_compare:
        lda _udeks_banked_legacy_names,y
        cmp _udeks_banked_graphics_names,x
        beq :+
        jmp legacy_not_ready
:       cmp #0
        beq legacy_match
        inx
        iny
        bne legacy_compare
legacy_match:
        txa
        lsr a
        lsr a
        lsr a
        lsr a
        jmp _udeks_banked_graphics_stop
