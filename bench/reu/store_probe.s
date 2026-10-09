; SPDX-License-Identifier: GPL-3.0-or-later
; Standalone destructive qualification. NEVER load into a running UDEKS.
        .setcpu "6502"
        .import _store_probe, __BSS_RUN__, __BSS_SIZE__, zerobss
        .import _udeks_reu_request
        .importzp sp, ptr1
        .export _store_to_bank1, _store_from_bank1, _store_bank1_guards
        .export _store_result := $7000
q = _udeks_reu_request
GATE = $f100
        .segment "STARTUP"
entry:  sei
        cld
        ldx #$ff
        txs
        lda #$3e
        sta $ff00
        sta $d501
        lda #$7e
        sta $d503
        lda #0
        sta $d508
        sta $d507
        sta $d50a
        sta $d030
        lda #1
        sta $d509
        lda #9
        sta $d506
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #0
        sta $d01a
        lda #<interrupt
        sta $fffa
        sta $fffe
        lda #>interrupt
        sta $fffb
        sta $ffff
        lda #0
        sta sp
        lda #$6f
        sta sp+1
        jsr zerobss
        ldx #common_end-common-1
copy:   lda common,x
        sta GATE,x
        dex
        bpl copy
        jsr GATE+(setup-common)
        jsr _store_probe
halt:   jmp halt
interrupt: rti

        .segment "CODE"
_store_to_bank1:
        sta ptr1
        stx ptr1+1
        jmp GATE+(stash-common)
_store_from_bank1:
        sta ptr1
        stx ptr1+1
        jmp GATE+(fetch-common)
_store_bank1_guards:
        jmp GATE+(guards-common)

; Active CPU bank stays 0 except for each bounded bank copy. CPU ZP/stack
; remain physical bank 0; no kernel or scheduler callbacks. Length 1..256.
common:
stash:  ldy #0
:       lda (ptr1),y
        sta $ff03
        sta $6000,y
        sta $ff01
        iny
        cpy q+7
        bne :-
        rts
fetch:  ldy #0
:       sta $ff03
        lda $6000,y
        sta $ff01
        sta (ptr1),y
        iny
        cpy q+7
        bne :-
        rts
setup:  sta $ff03
        lda #$5a
        sta $5fff
        lda #$a5
        sta $6100
        sta $ff01
        rts
guards: sta $ff03
        lda $5fff
        cmp #$5a
        bne :+
        lda $6100
        cmp #$a5
:       sta $ff01
        beq :+
        lda #1
        rts
:       lda #0
        rts
common_end:
        .assert common_end-common <= 128, error, "probe common gate grew"
