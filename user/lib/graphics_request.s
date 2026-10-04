; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .ifndef UDEKS_GFX_ABI
UDEKS_GFX_ABI = 9
        .endif
        .export _gfx_request, _gfx_sleep
        ; Absolute data bindings carry no storage or relocation into an app.
        .export _udeks_graphics_record = $f359
        .export _udeks_time_snapshot = $f200
        .segment "CODE"
_gfx_request:
        sta $f367
        lda #24
        sta $f363
        lda #23
        bne request
_gfx_sleep:
        lda #2
        sta $f367
        sta $f363
        lda #0
        sta $f368
        lda #13
request:
        sta $f360
        ldx #5
copy:   lda signature,x
        sta $f359,x
        dex
        bpl copy
        lda #0
        sta $f362
        sta $f366
        lda #1
        sta $f35f
        inc $f361
        jsr $ff16
        lda $f365
        ldx #0
        rts
        .segment "RODATA"
signature: .byte "UTRQ",0,UDEKS_GFX_ABI
