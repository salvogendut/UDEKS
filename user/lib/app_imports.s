; SPDX-License-Identifier: GPL-3.0-or-later
;
; Link-time names for the fixed UAPP 0.1 table. No private resident symbol is
; imported by a graphical UDEX image.

        .setcpu "6502"

        .exportzp sp, sreg, regsave, regbank
        .exportzp ptr1, ptr2, ptr3, ptr4
        .exportzp tmp1, tmp2, tmp3, tmp4
sp      = $06
sreg    = $08
regsave = $0a
ptr1    = $0e
ptr2    = $10
ptr3    = $12
ptr4    = $14
tmp1    = $16
tmp2    = $17
tmp3    = $18
tmp4    = $19
regbank = $1a

        .export _udeks_time_now
        .export _udeks_vic_bitmap_fill
        .export _udeks_vic_bitmap_line
        .export _udeks_vic_bitmap_pixel
        .export _udeks_vic_graphics_is_active
        .export _udeks_window_create
        .export _udeks_window_destroy
        .export _udeks_window_get_geometry
        .export _udeks_window_is_dragging
        .export _udeks_window_is_focused
        .export _udeks_window_repaint
        .export _udeks_z80_submit

_udeks_time_now                 = $cf60
_udeks_vic_bitmap_fill          = $cf63
_udeks_vic_bitmap_line          = $cf66
_udeks_vic_bitmap_pixel         = $cf69
_udeks_vic_graphics_is_active   = $cf6c
_udeks_window_create            = $cf6f
_udeks_window_destroy           = $cf72
_udeks_window_get_geometry      = $cf75
_udeks_window_is_dragging       = $cf78
_udeks_window_is_focused        = $cf7b
_udeks_window_repaint           = $cf7e
_udeks_z80_submit               = $cf81

        .export addeqysp, addysp, aslax2
        .export decsp1, decsp2, decsp3, decsp4, decsp5, decsp6, decsp7, decsp8
        .export incsp1, incsp2, incsp3, incsp4, incsp5, incsp6, incsp7
        .export ldaidx, mulax5, pusha, pusha0, pushax, pushwysp
        .export shrax1, shrax2, shrax4
        .export staspidx, stax0sp, staxysp, subysp
        .export tosaddax, tosicmp, tossuba0, tossubax
        .export tosudiva0, tosumoda0, tosumula0, tosumulax

addysp      = $cf84
aslax2      = $cf87
decsp1      = $cf8a
decsp2      = $cf8d
decsp3      = $cf90
decsp4      = $cf93
decsp5      = $cf96
decsp6      = $cf99
decsp7      = $cf9c
decsp8      = $cf9f
incsp1      = $cfa2
incsp2      = $cfa5
incsp3      = $cfa8
incsp4      = $cfab
incsp5      = $cfae
incsp6      = $cfb1
incsp7      = $cfb4
ldaidx      = $cfb7
mulax5      = $cfba
pusha       = $cfbd
pusha0      = $cfc0
pushax      = $cfc3
pushwysp    = $cfc6
shrax1      = $cfc9
shrax2      = $cfcc
shrax4      = $cfcf
staspidx    = $cfd2
stax0sp     = $cfd5
staxysp     = $cfd8
subysp      = $cfdb
tosaddax    = $cfde
tosicmp     = $cfe1
tossuba0    = $cfe4
tossubax    = $cfe7
tosudiva0   = $cfea
tosumoda0   = $cfed
tosumula0   = $cff0
tosumulax   = $cff3
addeqysp    = $cff6
