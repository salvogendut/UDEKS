; SPDX-License-Identifier: GPL-3.0-or-later
        .export _udeks_graphics_record = $f359
        .setcpu "6502"
        .export _udeks_banked_call, _udeks_banked_read, _udeks_banked_write
        .export _udeks_banked_graphics_exec
        .import _udeks_banked_graphics_launch
        .import _udeks_banked_graphics_installed, _udeks_banked_graphics_stop
        .import _udeks_console_start_once
        .export _udeks_console_start
        .include "../app/native_layout.inc"
        .export _udeks_banked_pages_init
        .export _udeks_native_base_pages, _udeks_native_stack_pages
        .importzp ptr1
        .segment "GRAPHICSHELP"
; The glyph source is retired after the lazy graphics install. Never upload
; those bytes (or invoke the retired boot composer) again. This BSS flag is
; cleared by crt0, unlike an arbitrary power-on diagnostic-record byte.
_udeks_console_start:
        lda _udeks_banked_graphics_installed
        beq :+
        lda #0
        tax
        rts
:       jmp _udeks_console_start_once
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

; Private, IRQ-masked bank-0 entry. X is a validated allocation index,
; A its effective stack page. Publish the same bound used by the loader to
; retained-source validation before the task becomes runnable. A free task's
; table entry is not authoritative; every activation refreshes it.
; No stack or ZP-dependent instruction/call while the task pages are mapped.
; Unlike absolute worker-bank stores, this also initializes physical pages
; $00/$01 without accidentally overwriting the resident kernel's page zero.
        .segment "MODULECODE"
_udeks_banked_pages_init:
        sta _udeks_native_stack_pages,x
        lda #1
        sta $d508
        sta $d50a
        lda native_zero,x
        sta $d507
        lda native_hardware,x
        sta $d509
        ; $00/$01 are the 8502 CPU port, not task scratch. Leave them alone.
        ldy #2
        lda #0
clear_native_pages:
        sta $0000,y
        sta $0100,y
        iny
        bne clear_native_pages
        lda #$a5
        sta $0100
        lda #$b0
        sta $02
        lda _udeks_native_stack_pages,x
        sta $03
        sta $01ff
        lda #$bf
        sta $01fe
        lda #0
        sta $d508
        sta $d507
        sta $d50a
        lda #1
        sta $d509
        rts
        .segment "MODULERODATA"
_udeks_native_base_pages: native_bases
_udeks_native_stack_pages: native_stacks
native_zero: native_zero_pages
native_hardware: native_hardware_pages
