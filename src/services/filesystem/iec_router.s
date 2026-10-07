; SPDX-License-Identifier: GPL-3.0-or-later
; Bank-0 dispatcher and trusted retirement hook. The permanent common gate
; owns only mapping/runtime transport; filesystem policy stays in bank 1.
        .setcpu "6502"
        .include "disk-loader-bindings.inc"
        .segment "CODE"
router: jmp request
        jmp retire                  ; $C883: A=context tag, preserves A/X/Y/P
request:
        php
        sei
        lda STORAGE_CURRENT_TASK
        bne selected
        ldx #10                     ; root loader/bootstrap, no running task
        lda $f285                   ; synchronous foreground invocation?
        cmp #2
        bne :+
        dex                         ; tag 9 is never the native shell instance
:       txa
selected:
        ldy #$0f                    ; private context request at $120F
        jsr $fe20
        plp
        cmp #0
        beq fallback
        cmp #$ff
        beq unavailable
        lda #0
        clc
        rts
unavailable:
        lda #5
        jmp STORAGE_FINISH_ERROR
fallback:
        jmp $f3ef
retire:
        php
        sei
        pha
        txa
        pha
        tya
        pha
        tsx
        lda $0103,x                 ; original A, trusted task/tag
        ldy #$12                    ; retire before slot/storage is reclaimed
        jsr $fe20
        pla
        tay
        pla
        tax
        pla
        plp
        rts
        .assert router = $c880, lderror, "storage router moved"
        .assert * <= $c900, lderror, "storage router reaches lifecycle handler"
