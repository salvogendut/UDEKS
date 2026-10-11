; SPDX-License-Identifier: GPL-3.0-or-later
; Bank-0 hidden graphics module. IRQ trampoline saves/restores CR, and the
; common NMI stub only marks pending. Long C/render work keeps IRQs enabled.
; Only bounded cross-bank copies/DMA borrow the backed-up bootfs page $F400.
        .setcpu "6502"
        .import _udeks_bitmap_request_hidden, _udeks_bitmap_paint_hidden
        .import _udeks_bitmap_release_hidden, _udeks_vic_graphics_start
        .import _udeks_bitmap_transfer_buffer
        .import _udeks_reu_request, _udeks_reu_transfer, _udeks_reu_discover
        .import _udeks_reu_capacity_banks, _udeks_reu_store_init
        .import _udeks_vic_buffer_restore, _udeks_nmi_drain
        .importzp ptr1
        .export _udeks_retained_bitmap_request, _udeks_retained_bitmap_paint
        .export _udeks_bitmap_release, _udeks_bitmap_display_start
        .export _udeks_bitmap_io_gate
q = _udeks_reu_request
RUN = $f400
        .segment "BSS"
error: .res 1
sum:   .res 2
        .segment "CODE"
_udeks_retained_bitmap_request:
        sta $ff02
        jsr _udeks_bitmap_request_hidden
        sta $ff01
        rts
_udeks_retained_bitmap_paint:
        sta $ff02
        jsr _udeks_bitmap_paint_hidden
        sta $ff01
        rts
_udeks_bitmap_release:
        sta $ff02
        jsr _udeks_bitmap_release_hidden
        sta $ff01
        rts

_udeks_bitmap_display_start:
        php
        sei
        lda #0
        sta sum
        sta sum+1
        ldx #boot_end-boot_image-1
:       lda boot_image,x
        sta RUN,x
        dex
        bpl :-
        jsr RUN                   ; returns IO, restores borrowed bootfs page
        sta $ff02
        ldx #5
:       lda $dff0,x
        cmp identity,x
        bne bad_image
        dex
        bpl :-
        lda sum
        cmp $dff6
        bne bad_image
        lda sum+1
        cmp $dff7
        bne bad_image
        sta $ff01
        plp
        ; Discovery is before xinit/any client, so bank-0 DMA is safe here.
        ; An absent/faulty device selects the unchanged internal backend.
        jsr _udeks_reu_discover
        lda _udeks_reu_capacity_banks
        sta $ff02
        jsr _udeks_reu_store_init
        sta $ff01
        jmp _udeks_vic_graphics_start
bad_image:
        sta $ff01
        plp
        lda #5
        ldx #0
        rts
identity: .byte "RBMP",0,1

; Source is a boot-only secondary-payload interval, consumed before xinit
; or native slot 5 can overwrite it. No stage-1/common-gate growth needed.
boot_image:
        ldx #16
        ldy #0
boot_byte:
        sta $ff04
boot_load:
        lda $7300,y
        sta $ff02
boot_store:
        sta $d000,y
        cpx #1
        bne boot_sum
        cpy #$f0
        bcs boot_next             ; trailer isn't included in its checksum
boot_sum:
        clc
        adc sum
        sta sum
        bcc boot_next
        inc sum+1
boot_next:
        iny
        bne boot_byte
        inc RUN+(boot_load-boot_image)+2
        inc RUN+(boot_store-boot_image)+2
        dex
        bne boot_byte
        sta $ff03
        jmp _udeks_vic_buffer_restore
boot_end:
        .assert boot_end-boot_image < 128, error, "boot copy exceeds loop bound"

_udeks_bitmap_io_gate:
        php
        sei
        sta $ff01
        jsr _udeks_nmi_drain
        sta $ff02
        jsr prepare_io
        jsr RUN
        sta $ff02
        lda error
        ldx #0
        plp
        rts

        .segment "BITMAPCODE"
prepare_io:
        ldx #io_end-io_image-1
:       lda io_image,x
        sta RUN,x
        dex
        bpl :-
        lda _udeks_bitmap_transfer_buffer
        sta ptr1
        lda _udeks_bitmap_transfer_buffer+1
        sta ptr1+1
        rts
io_image:
        lda q
        bne io_dma
        ldy #0
io_stash:
        lda (ptr1),y
        sta $ff03
        sta $4180,y
        sta $ff02
        iny
        cpy q+7
        bne io_stash
io_dma:
        sta $ff01
        jsr _udeks_reu_transfer
        sta error
        cmp #0                    ; transport preserves P, not return-value Z
        bne io_done
        lda q
        beq io_done
        ldy #0
io_fetch:
        sta $ff03
        lda $4180,y
        sta $ff02
        sta (ptr1),y
        iny
        cpy q+7
        bne io_fetch
io_done:
        sta $ff03
        jmp _udeks_vic_buffer_restore
io_end:
        .assert io_end-io_image < 128, error, "runtime copy exceeds loop bound"
        .segment "BITMAPID"
        .byte "RBMP",0,1
        .word 0                   ; sealed after link; sum of first $FF0 bytes
        .res 8,0
