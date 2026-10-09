; SPDX-License-Identifier: GPL-3.0-or-later
; Standalone, destructive scratch-RAM/REU proof. NEVER run inside UDEKS.
; Harness supplies number of 64K REU banks at $70F0 (0 = absent).
; Uses host $4FFF-$5100 in BOTH banks, REU boundary blocks and $100/bank.
        .setcpu "6502"
        .import _udeks_reu_transfer, _udeks_reu_request
        .import _udeks_reu_discover, _udeks_reu_capacity_banks
        .importzp sp
        .export entry
q = _udeks_reu_request
R = $7000
CONFIG = $70f0
PTR = $fa
STORE = $f100
LOAD = $f110

        .segment "STARTUP"
entry:
        sei
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
        ldx #31
copy:   lda common,x
        sta STORE,x
        lda #0
        sta R,x
        dex
        bpl copy
        ldx #3
magic:  lda identity,x
        sta R,x
        dex
        bpl magic
        lda #1
        sta R+4
        sta R+5
        lda CONFIG
        sta R+7
        lda #$6f
        sta sp+1
        lda #0
        sta sp
        jsr _udeks_reu_discover
        sta R+15
        lda _udeks_reu_capacity_banks
        sta R+14
        lda CONFIG
        beq no_capacity
        cmp #8
        bcc :+
        lda #8
:       cmp R+14
        bne bad_capacity
        lda R+15
        bne bad_capacity
        beq capacity_done
no_capacity:
        lda R+14
        bne bad_capacity
        lda R+15
        cmp #19
        beq capacity_done
bad_capacity:
        lda #15
        jmp fail
capacity_done:
        jsr defaults
        lda #4
        sta expected_flags
        lda #9
        sta expected_rcr
        lda #0
        sta expected_speed
        sta $d030
        jsr call
        lda CONFIG
        bne present
        lda observed
        cmp #19
        beq complete
        lda #1
        jmp fail
present:
        lda observed
        beq start_tests
        lda #2
        jmp fail
start_tests:
        jsr distinct_banks
        ; Probe again over known nonzero contents, then independently verify
        ; every bank tag survived discovery. Do not trust its self-check alone.
        jsr _udeks_reu_discover
        cmp #0
        beq :+
        lda #16
        jmp fail
:       jsr defaults
        lda #1
        sta q
        sta q+5
        lda #0
        sta bank_index
capacity_preserved:
        lda bank_index
        sta q+6
        jsr transfer
        lda bank_index
        eor #$a5
        cmp $5000
        beq :+
        lda #17
        jmp fail
:       inc R+16
        inc bank_index
        lda bank_index
        cmp CONFIG
        bne capacity_preserved
        lda #0
        sta scenario
scenario_loop:
        lda #0
        sta length_index
length_loop:
        jsr roundtrip
        inc R+8
        inc length_index
        lda length_index
        cmp #4
        bne length_loop
        inc scenario
        lda scenario
        cmp #32
        bne scenario_loop
        jsr rejections
complete:
        lda #2
        sta R+5
halt:   jmp halt
fail:   sta R+6
        lda #$80
        sta R+5
        jmp halt
interrupt:
        rti

; Common copy/read helpers. Page zero/stack remain pinned to bank 0.
; A byte, Y offset; X host bank; PTR kernel-owned. Code is standalone scratch.
common:
        cpx #0
        beq :+
        sta $ff03
:       sta (PTR),y
        sta $ff01
        rts
        .res 16-(*-common), $ea
        cpx #0
        beq :+
        sta $ff03
:       lda (PTR),y
        sta $ff01
        rts
        .res 32-(*-common), $ea

        .segment "CODE"
defaults:
        lda #0
        ldx #8
:       sta q,x
        dex
        bpl :-
        lda #$50
        sta q+3
        sta PTR+1
        lda #0
        sta PTR
        lda #1
        sta q+7
        rts

; Check every call, including negative requests, with independent expectations.
call:
        lda expected_flags
        ora #$20
        pha
        plp
        jsr _udeks_reu_transfer
        sta observed
        stx observed_x
        php
        pla
        and #$0c
        sta observed_flags
        sei
        cld
        lda observed_flags
        cmp expected_flags
        beq :+
        lda #3
        jmp fail
:       lda observed_x
        beq :+
        lda #4
        jmp fail
:       lda $ff00
        cmp #$3e
        beq :+
        lda #5
        jmp fail
:       lda $d506
        cmp expected_rcr
        beq :+
        lda #6
        jmp fail
:       lda $d030
        and #1
        cmp expected_speed
        beq :+
        lda #7
        jmp fail
:       inc R+10
        bne :+
        inc R+11
:       rts
transfer:
        jsr call
        lda observed
        beq :+
        lda #8
        jmp fail
:       rts

; Independent data at every configured 64K bank, not just same-address echo.
; This test owns the REU and deliberately overwrites one byte per bank.
distinct_banks:
        jsr defaults
        lda #1
        sta q+5
        lda #0
        sta bank_index
stash_bank:
        lda bank_index
        sta q+6
        eor #$a5
        sta $5000
        jsr transfer
        inc bank_index
        lda bank_index
        cmp CONFIG
        bne stash_bank
        lda #0
        sta bank_index
        lda #1
        sta q
fetch_bank:
        lda bank_index
        sta q+6
        lda #0
        sta $5000
        jsr transfer
        lda bank_index
        eor #$a5
        cmp $5000
        beq :+
        lda #9
        jmp fail
:       inc R+13
        inc bank_index
        lda bank_index
        cmp CONFIG
        bne fetch_bank
        rts

roundtrip:
        jsr defaults
        lda scenario
        and #1
        sta q+1
        lda scenario
        and #2
        asl a
        asl a
        asl a
        asl a
        asl a
        ora #9
        sta expected_rcr
        sta $d506
        lda scenario
        lsr a
        lsr a
        and #1
        sta expected_speed
        sta $d030
        lda scenario
        lsr a
        and #$0c
        sta expected_flags
        ldx length_index
        lda lengths,x
        sta q+7
        lda #0
        sta q+8
        cpx #3
        bne :+
        inc q+8
:       lda #$ff
        sta q+5
        ; Alternate between a cross-64K transfer and final expansion page.
        lda scenario
        and #1
        beq crossing
        lda CONFIG
        sec
        sbc #1
        sta q+6
        jmp fill
crossing:
        lda #$f0
        sta q+4
fill:
        ldy #0
:       ldx #0
        tya
        eor #$55
        jsr STORE
        ldx #1
        tya
        eor #$aa
        jsr STORE
        iny
        bne :-
        ; Both guards, in both physical RAM banks.
        lda #$ff
        sta PTR
        lda #$4f
        sta PTR+1
        jsr set_guard
        lda #0
        sta PTR
        lda #$51
        sta PTR+1
        jsr set_guard
        lda #$50
        sta PTR+1
        jsr transfer                 ; stash patterned source
        ldy #0
:       ldx q+1
        lda #$3c
        jsr STORE
        iny
        bne :-
        lda #1
        sta q
        jsr transfer                 ; fetch into cleared target, peer intact
        ldy #0
compare:
        lda #$3c
        sta expected_byte
        lda q+8
        bne pattern
        cpy q+7
        bcs check_target
pattern:
        lda q+1
        beq pattern0
        tya
        eor #$aa
        jmp pattern_ready
pattern0:
        tya
        eor #$55
pattern_ready:
        sta expected_byte
check_target:
        ldx q+1
        jsr LOAD
        cmp expected_byte
        beq :+
        lda #10
        jmp fail
:       lda q+1
        eor #1
        tax
        beq peer0
        tya
        eor #$aa
        jmp peer_ready
peer0:  tya
        eor #$55
peer_ready:
        sta expected_byte
        jsr LOAD
        cmp expected_byte
        beq :+
        lda #11
        jmp fail
:       iny
        bne compare
        lda #$ff
        sta PTR
        lda #$4f
        sta PTR+1
        jsr check_guard
        lda #0
        sta PTR
        lda #$51
        sta PTR+1
        jsr check_guard
        rts
set_guard:
        ldy #0
        ldx #0
        lda #$c7
        jsr STORE
        inx
        jmp STORE
check_guard:
        ldy #0
        ldx #0
        jsr LOAD
        cmp #$c7
        bne bad_guard
        inx
        jsr LOAD
        cmp #$c7
        bne bad_guard
        rts
bad_guard:
        lda #12
        jmp fail

rejections:
        lda #0
        sta bad_index
reject_loop:
        jsr defaults
        lda #19
        sta q+7
        ldx bad_index
        lda bad_offsets,x
        tay
        lda bad_values,x
        sta q,y
        ; Cases needing more than a one-byte modification.
        cpx #5                       ; host $CFFF + 19 crosses into IO
        bne :+
        lda #$ff
        sta q+2
:       cpx #6                       ; 24-bit expansion wrap
        bne :+
        lda #$ff
        sta q+4
        sta q+5
:       ldx #8
snapshot:
        lda q,x
        sta request_before,x
        lda $df02,x
        sta registers_before,x
        dex
        bpl snapshot
        jsr call
        lda observed
        cmp #22
        beq :+
        lda #13
        jmp fail
:       ldx #8
unchanged:
        lda q,x
        cmp request_before,x
        bne mutated
        lda $df02,x
        cmp registers_before,x
        bne mutated
        dex
        bpl unchanged
        inc R+12
        inc bad_index
        lda bad_index
        cmp #8
        bne reject_loop
        rts
mutated:
        lda #14
        jmp fail

        .segment "RODATA"
identity: .byte "REUQ"
lengths: .byte 1,19,255,0
bad_offsets: .byte 0,1,7,8,3,3,6,3
bad_values:  .byte 2,2,0,1,1,$cf,$ff,$ff
        .segment "BSS"
scenario: .res 1
length_index: .res 1
bank_index: .res 1
bad_index: .res 1
expected_flags: .res 1
expected_rcr: .res 1
expected_speed: .res 1
expected_byte: .res 1
observed: .res 1
observed_flags: .res 1
observed_x: .res 1
request_before: .res 9
registers_before: .res 9
