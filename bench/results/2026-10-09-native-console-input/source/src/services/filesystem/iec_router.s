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
        .ifdef UDEKS_DISK_TIME
        beq root_context
        cmp #9                     ; native ids are 1..8, never tag 9/10
        bcc selected
        lda #$ff                   ; corrupt/out-of-range native id is denied
        bne selected
root_context:
        .else
        bne selected
        .endif
        ldx #10                     ; root loader/bootstrap, no running task
        lda $f285                   ; synchronous foreground invocation?
        cmp #2
        bne :+
        dex                         ; tag 9 is never the native shell instance
:       txa
selected:
        .ifdef UDEKS_DISK_TIME
        ldx $f360
        cpx #28
        beq module_request
        .endif
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
        .ifdef UDEKS_DISK_TIME
module_request:
        plp                         ; C service runs with caller's IRQ state
        jmp TIME_MODULE_REQUEST     ; A retains the trusted context tag
        .endif
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
        .ifdef UDEKS_DISK_TIME
        cmp #9
        bne :+
        jsr $cf33                   ; abort ONLY a loading foreground lease
        lda #9
:
        .endif
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
        ; Private bank-0 caller query for terminal ownership. No task-supplied
        ; id is trusted; the binding comes from the actual scheduler map.
        .assert * <= $c8fc, lderror, "storage router reaches caller query"
        .res $7c-(*-router), $ea
        lda STORAGE_CURRENT_TASK
        rts
