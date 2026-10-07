; SPDX-License-Identifier: GPL-3.0-or-later
; Standalone mapping/NMI proof, NOT a boot service. Owns both RAM banks.
; $7000 record, $7040 private pending flag, $8000 saved common preimage.
        .setcpu "6502"
        .include "nmi-common.inc"
        .segment "CODE"
R = $7000
PENDING = $7040
WINDOW = $7041
ROUND = $7042
SAVED_RCR = $7043
COPY = $f680
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
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #0
        sta $d01a
        sta $dd0e
        ; Pin page zero and page one to bank 0 for this standalone proof.
        sta $d508
        sta $d507
        sta $d50a
        lda #1
        sta $d509
        lda $70f0                 ; harness: 0 or $40, VIC bank selection
        and #$40
        ora #9
        sta $d506
        ; Fill all common bytes below the MMU page, then install the copier.
        lda #$f0
        sta fill_store+2
page:  ldy #0
fill:  tya
fill_store:
        sta $f000,y
        iny
        bne fill
        inc fill_store+2
        lda fill_store+2
        cmp #$ff
        bne page
        ldx #common_end-common-1
copy_common:
        lda common,x
        sta COPY,x
        dex
        bpl copy_common
        ; Copy this whole low-memory image to bank 1 while common is enabled.
        ; The same source/destination address in different physical banks.
        jmp COPY
common:
        ldy #0
load:  lda entry,y
        sta $ff03                 ; PCRs set below by launcher before copy
store: sta entry,y
        sta $ff01
        iny
        bne load
        inc COPY+(load+2-common)
        inc COPY+(store+2-common)
        lda COPY+(load+2-common)
        cmp #>image_end
        bcc load
        lda #$7e
        sta $ff00
        jmp worker
finish:
        ldx #31
collect:
        lda R,x
        sta $ff01
        sta R,x
        sta $ff03
        dex
        bpl collect
        sta $ff01
halt:  jmp COPY+(halt-common)
common_end:

worker:
        ldx #$7f
        lda #0
clear: sta R,x
        dex
        bpl clear
        lda #'S'
        sta R
        lda #'W'
        sta R+1
        lda #'I'
        sta R+2
        lda #'N'
        sta R+3
        lda #1
        sta R+4
        sta R+5
        lda $d506
        sta SAVED_RCR
        sta R+16
        ; Common NMI observer + unchanged production deferred-pending stub.
        ldx #observer_end-observer-1
install_observer:
        lda observer,x
        sta $ff20,x
        dex
        bpl install_observer
        ldx #7
install_stub:
        lda visible_stub,x
        sta $ffe2,x
        dex
        bpl install_stub
        lda #$20
        sta $fffa
        lda #$ff
        sta $fffb
        lda #0
        sta $fff5
        ; Save all common bytes $F000-$FEFF, including the active copier.
        lda #$f0
        sta snapshot_load+2
        lda #$80
        sta snapshot_store+2
snapshot_page:
        ldy #0
snapshot_load:
        lda $f000,y
snapshot_store:
        sta $8000,y
        iny
        bne snapshot_load
        inc snapshot_load+2
        inc snapshot_store+2
        lda snapshot_load+2
        cmp #$ff
        bne snapshot_page
        ; Initial mirror installation with all native CIA2 NMI sources masked
        ; and acknowledged. No cartridge-generated NMI qualification claimed.
        lda SAVED_RCR
        and #$f7
        sta $d506
        lda #$f0
        sta hidden_store+2
hidden_page:
        ldy #0
hidden_fill:
        tya
hidden_store:
        sta $f000,y
        iny
        bne hidden_fill
        inc hidden_store+2
        lda hidden_store+2
        cmp #$ff
        bne hidden_page
        ldx #observer_end-observer-1
install_hidden_observer:
        lda observer,x
        sta $ff20,x
        dex
        bpl install_hidden_observer
        ; Change the observer's count destination to the hidden counter.
        lda #<(R+10)
        sta $ff20+(observer_count+1-observer)
        lda #<(R+11)
        sta $ff20+(observer_count_high+1-observer)
        ldx #7
install_hidden_stub:
        lda hidden_stub,x
        sta $ffe2,x
        dex
        bpl install_hidden_stub
        lda #$20
        sta $fffa
        lda #$ff
        sta $fffb
        ldx #high_end-high-1
install_high:
        lda high,x
        sta $f000,x
        dex
        bpl install_high
        lda SAVED_RCR
        sta $d506
        lda #$81
        sta $dd0d

cycle:
        ; An NMI with common memory visible must publish to the real flag.
        lda #40
        jsr arm
        jsr delay
        lda $fff5
        bne visible_ok
        jmp fail_pending
visible_ok:
        lda #0
        sta $fff5
        sta PENDING
        lda $dd0d
        ; Keep all VIC-bank and size/bottom-common bits; change only bit 3.
        lda SAVED_RCR
        and #$f7
        sta $d506
        lda #40
        jsr arm
        ; Execute real instructions from the newly exposed physical RAM.
        lda #$35
        ldx #$76
        ldy #$ab
        sec
        jsr $f000
        php
        cmp #$35
        bne bad_register
        cpx #$76
        bne bad_register
        cpy #$ab
        bne bad_register
        pla
        and #1
        bne registers_ok
        jmp fail_register
bad_register:
        pla
        jmp fail_register
registers_ok:
        jsr delay
        lda PENDING
        bne hidden_ok
        jmp fail_pending
hidden_ok:
        jsr leave_window
        lda $fff5
        bne merged_ok
        jmp fail_pending
merged_ok:
        lda #0
        sta $fff5
        lda $dd0d
        ; Vary NMI timing across BOTH mapping boundaries. The observer marks
        ; this whole small window; counts are not a single-cycle timing claim.
        lda #1
        sta WINDOW
        lda ROUND
        and #$3f
        clc
        adc #1
        jsr arm
        lda SAVED_RCR
        and #$f7
        sta $d506
        nop
        nop
        nop
        jsr leave_window
        jsr delay
        lda $fff5
        bne boundary_ok
        jmp fail_pending
boundary_ok:
        lda #0
        sta WINDOW
        sta $fff5
        lda $dd0d
        lda $d506
        cmp SAVED_RCR
        beq mapping_ok
        jmp fail_mapping
mapping_ok:
        inc ROUND
        lda ROUND
        cmp #128
        beq cycles_done
        jmp cycle
cycles_done:
        ; Stop and acknowledge the timer before the final byte comparison.
        lda #0
        sta $dd0e
        lda #$7f
        sta $dd0d
        lda $dd0d
        lda #$f0
        sta compare_load+2
        lda #$80
        sta compare_saved+2
compare_page:
        ldy #0
compare_load:
        lda $f000,y
compare_saved:
        cmp $8000,y
        beq byte_ok
        jmp fail_common
byte_ok:
        iny
        bne compare_load
        inc compare_load+2
        inc compare_saved+2
        lda compare_load+2
        cmp #$ff
        bne compare_page
        lda $d506
        sta R+17
        lda $ff00
        sta R+18
        tsx
        stx R+19
        lda ROUND
        sta R+7
        lda PENDING
        sta R+21
        lda #2
        sta R+5
        jmp COPY+(finish-common)
fail_pending:
        lda #1
        bne failed
fail_register:
        lda #2
        bne failed
fail_mapping:
        lda #3
        bne failed
fail_common:
        lda #4
failed:
        sta R+6
        lda SAVED_RCR
        sta $d506
        lda #$80
        sta R+5
        jmp COPY+(finish-common)

; Critical ordering: expose common first, then sample the flag BELOW $F000.
; An NMI just before restoration still sets PENDING. An NMI after restoration
; sets $FFF5 directly. Never clear the shared flag during the merge.
leave_window:
        lda SAVED_RCR
        sta $d506
        lda PENDING
        beq leave_done
        lda #1
merge:  sta $fff5
        lda #0
        sta PENDING
leave_done:
        rts
arm:
        sta $dd04
        lda #0
        sta $dd05
        lda #$19                 ; one shot, force load, start
        sta $dd0e
        rts
delay:
        ldx #0
delay_loop:
        dex
        bne delay_loop
        rts
high:
        php
        pha
        txa
        pha
        tya
        pha
        lda #$a5
        sta R+20
        ldx #0
high_loop:
        dex
        bne high_loop
        pla
        tay
        pla
        tax
        pla
        plp
        rts
high_end:
observer:
        pha
observer_count:
        inc R+8
        bne :+
observer_count_high:
        inc R+9
:
        lda WINDOW
        beq :+
        inc R+12
        bne :+
        inc R+13
:
        pla
        jmp $ffe2
observer_end:
visible_stub:
        UDEKS_NMI_STUB
hidden_stub:
        pha
        lda #1
        sta PENDING
        pla
        rti
        .assert *-hidden_stub = 8, error, "hidden stub grew"
        .assert common_end-common < 128, error, "copier exceeds lease"
        .align 256
image_end:
