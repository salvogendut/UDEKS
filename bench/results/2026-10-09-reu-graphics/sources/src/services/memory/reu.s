; SPDX-License-Identifier: GPL-3.0-or-later
; Private, serialized 8502 REU transport candidate. NOT linked into boot yet.
; Caller owns REU and the entire physical host/expansion interval. No task
; pointers accepted here. Call in kernel IO profile $3E, never from IRQ/NMI.
; Request: direction (0=stash,1=fetch), host bank, host address LE,
;          expansion address LE24, count LE16. Count must be 1..256.
; Host interval restricted to $0200..$CFFF, excluding IO/common/page relocation.
; P (including I/D), CPU CR, RCR and speed are preserved. A = errno, X = 0.
; Exclusively owns REC registers; command/IRQ state is NOT restored/re-armed.
        .setcpu "6502"
        .export _udeks_reu_transfer, _udeks_reu_request

        .segment "BSS"
_udeks_reu_request: .res 9
last:              .res 2
saved_rcr:         .res 1
saved_speed:       .res 1
saved_address:     .res 1
result:            .res 1

        .segment "CODE"
q = _udeks_reu_request
_udeks_reu_transfer:
        php
        sei
        cld
        jsr validate
        bcc valid
        lda #22                     ; EINVAL, no IO touched
        jmp done
valid:  lda $df04                   ; reversible register-only presence test
        sta saved_address
        lda #$55
        sta $df04
        cmp $df04
        bne absent
        lda #$aa
        sta $df04
        cmp $df04
        bne absent
        lda saved_address
        sta $df04

        lda $d030
        sta saved_speed
        and #$fe
        sta $d030                   ; 8502 slow while REC owns the bus
        lda $d506
        sta saved_rcr
        and #$3f                    ; same VIC/DMA bank selector, bit 6
        ldx q+1
        beq bank_ready
        ora #$40
bank_ready:
        sta $d506                   ; never change common RAM / CPU mapping
        lda #0
        sta $df09                   ; no REC IRQ
        sta $df0a                   ; both addresses increment
        lda $df00                   ; acknowledge stale completion
        ldx #6
registers:
        lda q+2,x
        sta $df02,x
        dex
        bpl registers
        lda q
        ora #$90                    ; execute immediately, no $FF00 trigger
        sta $df01                   ; DMA stalls CPU until bounded block ends
        lda $df00
        and #$60
        cmp #$40                    ; end-of-block, no verify error
        beq success
        lda #5                      ; EIO
        bne restore
success:
        lda #0
restore:
        sta result
        lda saved_rcr
        sta $d506                   ; restore VIC bank before re-enabling IRQ
        lda saved_speed
        sta $d030
        lda result
        jmp done
absent:
        lda saved_address
        sta $df04
        lda #19                     ; ENODEV
done:   ldx #0
        plp
        rts

; All checks precede writes, even to REU registers. Return C=1 on rejection.
validate:
        lda $ff00
        cmp #$3e
        bne bad
        lda q
        cmp #2
        bcs bad
        lda q+1
        cmp #2
        bcs bad
        lda q+8
        beq short_count
        cmp #1
        bne bad
        lda q+7
        bne bad
        beq count_ok                ; 256, NOT the REC's 65536-byte zero count
short_count:
        lda q+7
        beq bad
count_ok:
        sec
        lda q+7
        sbc #1
        sta last
        lda q+8
        sbc #0
        sta last+1
        lda q+3
        cmp #2
        bcc bad
        clc
        lda q+2
        adc last
        lda q+3
        adc last+1
        bcs bad
        cmp #$d0
        bcs bad
        ; Prevent wrapping the 24-bit expansion address. Capacity/ownership
        ; are higher-level policy and must be checked before this primitive.
        clc
        lda q+4
        adc last
        lda q+5
        adc last+1
        lda q+6
        adc #0
        bcs bad
        clc
        rts
bad:    sec
        rts
