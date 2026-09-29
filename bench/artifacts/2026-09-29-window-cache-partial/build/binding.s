; SPDX-License-Identifier: GPL-3.0-or-later
; Experimental resident acceptance, guard and persistent ticket seam.
; No BSS/ZP borrowed. State lives in explicitly charged writable CODE bytes.
        .setcpu "6502"
        .include "layout.inc"
        .include "acceptance.inc"
        .import _cache_raw_call
        .import _udeks_nmi_drain
        .export _cache_accept_poll, _private_cache_policy_call, _cache_step
        .export _cache_accept_state, _cache_ticket, _cache_owner, _cache_phase
        .segment "CODE"
_cache_accept_poll:
        php
        sei
        cld
        lda _cache_accept_state
        bpl validate
        jmp return_state
validate:
        sta PARAM
        lda _cache_ticket
        sta PARAM+1
        lda _cache_ticket+1
        sta PARAM+2
        lda #$00                 ; zero count means a full 256-byte page
        ldx _cache_accept_state
        cpx #CACHE_LAST_PAGE
        bne :+
        lda #CACHE_LAST_BYTES
:
        sta PARAM+3
        lda #$00
        sta $f3ed                ; retire installed outline workspace marker
        ldx #$00
copy:
        lda validator_image,x
        sta RUN,x
        inx
        cpx #validator_end-validator_image
        bcc copy
        ; Kernel I/O is still selected and registers are disposable here.
        ; A pending edge during the copy must not mask all worker observations.
        jsr _udeks_nmi_drain
        jsr RUN
        lda RESULT
        bne rejected
        lda PARAM+1
        sta _cache_ticket
        lda PARAM+2
        sta _cache_ticket+1
        inc _cache_accept_state
        lda _cache_accept_state
        cmp #CACHE_LAST_PAGE+1
        bne pending
        lda _cache_ticket
        cmp #<CACHE_CHECKSUM
        bne rejected
        lda _cache_ticket+1
        cmp #>CACHE_CHECKSUM
        bne rejected
        lda #$80                 ; admit C only after header AND whole checksum
        sta _cache_accept_state
        lda #$00
        sta OP
        jsr _private_cache_policy_call
        cmp #$00
        bne rejected
        lda #$80
        bne return_state
rejected:
        lda #$ff
        sta _cache_accept_state
        bne return_state
pending:
        lda #$00
return_state:
        sta RESULT
        plp
        lda RESULT
        ldx #$00
        rts

_private_cache_policy_call:
        php
        sei
        lda _cache_accept_state
        cmp #$80
        bne blocked
        jsr _cache_raw_call
        cmp #$00
        bne done
        lda $f793
        sta _cache_ticket
        lda $f794
        sta _cache_ticket+1
        lda $f792
        sta _cache_owner
        lda $f791
        sta _cache_phase
done:
        plp
        lda RESULT
        ldx #$00
        rts
blocked:
        lda #$ff
        sta RESULT
        bne done

; The old common request may have been overwritten by any other VIC gateway.
; Reconstruct STEP from persistent original content ticket and window handle.
_cache_step:
        lda _cache_ticket
        sta $f793
        lda _cache_ticket+1
        sta $f794
        lda _cache_owner
        sta $f792
        lda #$04
        sta OP
        jmp _private_cache_policy_call

_cache_accept_state: .byte 0     ; pages0..15; $80 accepted, $FF disabled
_cache_ticket: .word 0          ; checksum until acceptance; content ticket after
_cache_owner: .byte 0
_cache_phase: .byte 0
validator_image:
        .incbin "build/bench/window-cache-partial/acceptance/validator.bin"
validator_end:
