; SPDX-License-Identifier: GPL-3.0-or-later
; UAPP public entries. xcalc links its own arithmetic runtime helpers: mixing
; partially exported none.lib modules with the resident aliases duplicates
; symbols when 32-bit arithmetic pulls in multi-entry library objects.
        .exportzp sp, sreg, regsave, regbank, ptr1, ptr2, ptr3, ptr4
        .exportzp tmp1, tmp2, tmp3, tmp4
sp=$06
sreg=$08
regsave=$0a
ptr1=$0e
ptr2=$10
ptr3=$12
ptr4=$14
tmp1=$16
tmp2=$17
tmp3=$18
tmp4=$19
regbank=$1a
        .export _udeks_vic_bitmap_fill, _udeks_vic_bitmap_line
        .export _udeks_window_create, _udeks_window_destroy
        .export _udeks_window_get_geometry, _udeks_window_is_focused
        .export _udeks_window_begin_paint, _udeks_window_end_paint
_udeks_vic_bitmap_fill=$cf63
_udeks_vic_bitmap_line=$cf66
_udeks_window_create=$cf6f
_udeks_window_destroy=$cf72
_udeks_window_get_geometry=$cf75
_udeks_window_is_focused=$cf7b
_udeks_window_begin_paint=$cff9
_udeks_window_end_paint=$cffc
