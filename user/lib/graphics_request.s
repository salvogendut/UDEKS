; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .ifndef UDEKS_GFX_ABI
UDEKS_GFX_ABI = 9
        .endif
        .export _gfx_request, _gfx_sleep
        .if UDEKS_GFX_ABI >= 12
        .export _gfx_yield
        .endif
        ; Absolute data bindings carry no storage or relocation into an app.
        .export _udeks_graphics_record = $f359
        .export _udeks_time_snapshot = $f200
        .segment "CODE"
        .if UDEKS_GFX_ABI >= 11
        .export _worker_request
        .export _udeks_worker_output = $f300
_worker_request:
        lda #4
        sta $f363
        lda #24
        bne request
        .endif
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
        bne request
        .if UDEKS_GFX_ABI >= 12
_gfx_yield:
        lda #0
        sta $f363
        lda #10
        .endif
request:
        .if UDEKS_GFX_ABI >= 14
        ldx #0
        stx $f362
        ; Native file clients set descriptor/count/payload before entry.
        ; Same FF16 gate and private cc65 context, never the CF30 console ABI.
        .export _native_file_request
_native_file_request:
        .endif
        sta $f360
        ldx #5
copy:   lda signature,x
        sta $f359,x
        dex
        bpl copy
        lda #0
        .if UDEKS_GFX_ABI < 14
        sta $f362
        .endif
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
