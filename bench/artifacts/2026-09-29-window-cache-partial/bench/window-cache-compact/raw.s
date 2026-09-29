; SPDX-License-Identifier: GPL-3.0-or-later
; Called only behind acceptance + serialized resident guard. Gateway SOURCE
; is part of the initially checksummed bank-1 module, never a live app slot.
        .setcpu "6502"
        .include "layout.inc"
        .include "loader.inc"
        .import _udeks_nmi_drain, _cache_copy_fault_probe
        .export _cache_raw_call
LOADER = RUN+$d0
        .segment "CODE"
_cache_raw_call:
        php
        sei
        lda #$00
        sta $f3ed
        ldx #loader_end-loader_image-1
install:
        lda loader_image,x
        sta LOADER,x
        dex
        bpl install
        jsr _udeks_nmi_drain
        jsr LOADER
        ; Diagnostic-only identity writes. Keep the call charged in this
        ; measured closure; never infer a production fit by subtracting it.
        jsr _cache_copy_fault_probe
        plp
        jmp RUN
loader_image:
        sta WORKER
        ldx #$00
copy:
        lda GATE_SOURCE,x
        sta RUN,x
        inx
        cpx #GATE_BYTES
        bcc copy
        sta KERNEL
        rts
loader_end:
        .assert GATE_BYTES <= $d0, error, "gateway overwrites active loader"
        .assert LOADER+loader_end-loader_image <= PARAM, error, "loader reaches parameters"
        .assert loader_end-loader_image <= $80, error, "loader exceeds signed installer"
