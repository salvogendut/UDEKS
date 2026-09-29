; SPDX-License-Identifier: GPL-3.0-or-later
; Diagnostic observer precedes the exact production stub. Never installed in
; a normal boot image; $FF20/$FF80 are free ONLY in this standalone PRG.
        .setcpu "6502"
        .include "nmi-common.inc"
        .import _udeks_nmi_start, _udeks_nmi_drain
        .export _nmi_probe_start, _nmi_probe_stop, _nmi_probe_publish
COUNT = $f796                    ; observer counters, not production state
WORKER_COUNT = $f7a7
WRAPPER = $ff20
RECORD = $7fc0
        .segment "CODE"
_nmi_probe_start:
        php
        sei
        jsr _udeks_nmi_start
        lda #$5a
        sta $ffea
        sta $fff8
        lda #$a5
        sta $ffec
        sta $fff9
        lda #$00
        ldx #$03
clear:
        sta COUNT,x
        sta WORKER_COUNT,x
        dex
        bpl clear
        ldx #wrapper_end-wrapper-1
copy:
        lda wrapper,x
        sta WRAPPER,x
        dex
        bpl copy
        lda #<WRAPPER
        sta $fffa
        lda #>WRAPPER
        sta $fffb
        lda #$00
        sta $dd04
        lda #$04                ; CIA2 Timer A -> NMI, including worker leases
        sta $dd05
        lda #$81
        sta $dd0d
        lda #$11
        sta $dd0e
        plp
        rts
_nmi_probe_stop:
        php
        sei
        lda #$00
        sta $dd0e
        jsr _udeks_nmi_drain
        lda #$7f
        sta $dd0d
        lda $dd0d
        plp
        rts
_nmi_probe_publish:
        ldx #$03
publish:
        lda COUNT,x
        sta RECORD+26,x
        lda WORKER_COUNT,x
        sta RECORD+30,x
        dex
        bpl publish
        lda UDEKS_NMI_DRAINS
        sta RECORD+34
        lda UDEKS_NMI_DRAINS+1
        sta RECORD+35
        lda UDEKS_NMI_PENDING
        sta RECORD+36
        lda $ffea
        cmp #$5a
        bne bad_guard
        lda $ffec
        cmp #$a5
        bne bad_guard
        lda $fff8
        cmp #$5a
        bne bad_guard
        lda $fff9
        cmp #$a5
        beq guards_ok
bad_guard:
        lda #$01
        sta RECORD+37
guards_ok:
        rts
wrapper:
        pha
        inc COUNT
        bne :+
        inc COUNT+1
        bne :+
        inc COUNT+2
        bne :+
        inc COUNT+3
:
        lda $ff00
        cmp #$7f
        bne observed
        inc WORKER_COUNT
        bne observed
        inc WORKER_COUNT+1
        bne observed
        inc WORKER_COUNT+2
        bne observed
        inc WORKER_COUNT+3
observed:
        pla
        jmp UDEKS_NMI_ENTRY
wrapper_end:
        .assert WRAPPER+wrapper_end-wrapper < $ff80, error, "observer reaches IRQ"
