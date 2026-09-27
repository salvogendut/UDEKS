; SPDX-License-Identifier: GPL-3.0-or-later
;
; Fixed, compact call table for managed bank-0 graphical UDEX images. The
; applications use the resident cc65 zero-page layout and therefore may tail
; through these JMP vectors with the ordinary C calling convention.

        .setcpu "6502"
        .segment "SYSCALLS"

        .import _udeks_time_now
        .import _udeks_vic_bitmap_fill
        .import _udeks_vic_bitmap_line
        .import _udeks_vic_bitmap_pixel
        .import _udeks_vic_graphics_is_active
        .import _udeks_window_create
        .import _udeks_window_destroy
        .import _udeks_window_get_geometry
        .import _udeks_window_is_dragging
        .import _udeks_window_is_focused
        .import _udeks_window_repaint
        .import _udeks_z80_submit

        .import addeqysp, addysp, aslax2
        .import decsp1, decsp2, decsp3, decsp4, decsp5, decsp6, decsp7, decsp8
        .import incsp1, incsp2, incsp3, incsp4, incsp5, incsp6, incsp7
        .import ldaidx, mulax5, pusha, pusha0, pushax, pushwysp
        .import shrax1, shrax2, shrax4
        .import staspidx, stax0sp, staxysp, subysp
        .import tosaddax, tosicmp, tossuba0, tossubax
        .import tosudiva0, tosumoda0, tosumula0, tosumulax

        ; UAPP 0.1 publishes none.lib's runtime zero page at fixed addresses.
        ; Keep the linked symbols pinned so no new object can silently shift
        ; the layout that managed UDEX images were built against.
        .importzp sp, sreg, regsave, regbank
        .importzp ptr1, ptr2, ptr3, ptr4
        .importzp tmp1, tmp2, tmp3, tmp4
        .assert sp = $06, error, "UAPP 0.1 sp moved"
        .assert sreg = $08, error, "UAPP 0.1 sreg moved"
        .assert regsave = $0a, error, "UAPP 0.1 regsave moved"
        .assert ptr1 = $0e, error, "UAPP 0.1 ptr1 moved"
        .assert ptr2 = $10, error, "UAPP 0.1 ptr2 moved"
        .assert ptr3 = $12, error, "UAPP 0.1 ptr3 moved"
        .assert ptr4 = $14, error, "UAPP 0.1 ptr4 moved"
        .assert tmp1 = $16, error, "UAPP 0.1 tmp1 moved"
        .assert tmp2 = $17, error, "UAPP 0.1 tmp2 moved"
        .assert tmp3 = $18, error, "UAPP 0.1 tmp3 moved"
        .assert tmp4 = $19, error, "UAPP 0.1 tmp4 moved"
        .assert regbank = $1a, error, "UAPP 0.1 regbank moved"

_udeks_app_gateway:
        .assert _udeks_app_gateway = $cf50, error, "app gateway moved"
        .byte 'U', 'A', 'P', 'P'
        .byte $00, $01
        .byte $33, $03
        .res 8, $00

        jmp _udeks_time_now
        jmp _udeks_vic_bitmap_fill
        jmp _udeks_vic_bitmap_line
        jmp _udeks_vic_bitmap_pixel
        jmp _udeks_vic_graphics_is_active
        jmp _udeks_window_create
        jmp _udeks_window_destroy
        jmp _udeks_window_get_geometry
        jmp _udeks_window_is_dragging
        jmp _udeks_window_is_focused
        jmp _udeks_window_repaint
        jmp _udeks_z80_submit
        jmp addysp
        jmp aslax2
        jmp decsp1
        jmp decsp2
        jmp decsp3
        jmp decsp4
        jmp decsp5
        jmp decsp6
        jmp decsp7
        jmp decsp8
        jmp incsp1
        jmp incsp2
        jmp incsp3
        jmp incsp4
        jmp incsp5
        jmp incsp6
        jmp incsp7
        jmp ldaidx
        jmp mulax5
        jmp pusha
        jmp pusha0
        jmp pushax
        jmp pushwysp
        jmp shrax1
        jmp shrax2
        jmp shrax4
        jmp staspidx
        jmp stax0sp
        jmp staxysp
        jmp subysp
        jmp tosaddax
        jmp tosicmp
        jmp tossuba0
        jmp tossubax
        jmp tosudiva0
        jmp tosumoda0
        jmp tosumula0
        jmp tosumulax
        jmp addeqysp

        .assert * <= $d000, error, "app gateway overlaps I/O aperture"
