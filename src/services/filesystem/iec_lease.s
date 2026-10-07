; SPDX-License-Identifier: GPL-3.0-or-later
; Private bank-1 lease: standalone UIEC 0.2, production context entries 0.3.
; Entry requires worker-I/O ($7E), top-4K/no-bottom common, storage sp=$E200,
; and the hidden image already installed. P0/P1 are caller-owned, unchanged.
; AX = trusted instance, never derived from request bytes. No yield/Z80 lease.
        .setcpu "6502"
        .import _udeks_storage_dispatch, _udeks_storage_cleanup
        .import __BSS_RUN__, __BSS_SIZE__
        .export _udeks_storage_request, _udeks_storage_cwd
        .export _udeks_storage_boot_source, _udeks_storage_caller
        .export _udeks_storage_lease_pending
        .export _udeks_storage_lease_enter, _udeks_storage_lease_leave
        .export _udeks_storage_lease_merge

REQUEST = $f359
CWD = $f2a6
BOOT_SOURCE = $f3dd
NMI_PENDING = $fff5

        .segment "STARTUP"
        jmp request
        .ifdef UDEKS_STORAGE_CONTEXT
        .import _udeks_storage_context_request, _udeks_storage_context_retire
        .byte "UIEC", 0, 3
        .else
        .byte "UIEC", 0, 2
        .endif
        jmp cleanup
        jmp initialize
        .assert * = $120f, lderror, "storage lease vectors moved"
        .ifdef UDEKS_STORAGE_CONTEXT
        jmp _udeks_storage_context_request
        jmp _udeks_storage_context_retire
        .endif

        .segment "BSS"
_udeks_storage_request: .res 38
_udeks_storage_cwd: .res 1
_udeks_storage_boot_source: .res 1
instance: .res 2

        .segment "IECCODE"
; Initialized bytes in the driver image, separate from tightly bounded BSS.
ready: .byte 0
_udeks_storage_lease_pending: .byte 0
saved_rcr: .byte 0
operation: .byte 0
result: .byte 0

request:
        ldy #0
        beq enter
cleanup:
        ldy #1
enter:
        sta instance
        stx instance+1
        sty operation
        php
        sei
        cld
        lda ready
        beq reject
        jsr mapping
        bne reject
        lda operation
        bne prepared
        ldx #37
snapshot:
        lda REQUEST,x
        sta _udeks_storage_request,x
        dex
        bpl snapshot
        lda CWD
        sta _udeks_storage_cwd
        lda BOOT_SOURCE
        sta _udeks_storage_boot_source
prepared:
        lda #0
        sta _udeks_storage_lease_pending
        lda saved_rcr
        and #$f7
_udeks_storage_lease_enter:
        sta $d506
        lda operation
        bne clean
        jsr _udeks_storage_dispatch
        jmp restore
clean:
        lda instance
        ldx instance+1
        jsr _udeks_storage_cleanup
restore:
        sta result
        lda saved_rcr
_udeks_storage_lease_leave:
        sta $d506
        ; Restore common BEFORE sampling low pending: hidden NMIs up to the
        ; final mapping instruction survive. Visible NMIs publish directly.
        lda _udeks_storage_lease_pending
        beq merged
        lda #1
_udeks_storage_lease_merge:
        sta NMI_PENDING
        lda #0
        sta _udeks_storage_lease_pending
merged:
        lda operation
        bne done
        ldx #37
publish:
        lda _udeks_storage_request,x
        sta REQUEST,x
        dex
        bpl publish
        lda _udeks_storage_cwd
        sta CWD
done:
        lda result
        ldx #0
        plp
        rts
reject:
        lda #$ff                ; private gate failure, request untouched
        ldx #0
        plp
        rts

mapping:
        lda $ff00
        cmp #$7e
        bne mapped
        lda $d506
        sta saved_rcr
        and #$0f
        cmp #$09
mapped: rts

        .segment "STORAGECODE"
; Boot-only. Hidden image must be present, and native CIA2 sources must not
; yet be owned by input. Initialization leaves them masked; it does not try
; to reconstruct an unreadable previous CIA2 interrupt-enable mask.
initialize:
        php
        sei
        lda ready
        bne initialized
        jsr mapping
        beq :+
        jmp reject
:
        lda #$7f
        sta $dd0d
        lda $dd0d
        ldx #0
        lda #0
clear_page:
        sta __BSS_RUN__,x
        inx
        bne clear_page
        ldx #$80
clear_tail:
        dex
        sta __BSS_RUN__+$100,x
        bne clear_tail
        lda saved_rcr
        and #$f7
        sta $d506
        ldx #7
mirror:
        lda hidden_nmi,x
        sta $ffe2,x
        dex
        bpl mirror
        lda #$e2
        sta $fffa
        lda #$ff
        sta $fffb
        lda saved_rcr
        sta $d506
        inc ready
initialized:
        lda #0
        tax
        plp
        rts

        .segment "CODE"
_udeks_storage_caller:
        lda instance
        ldx instance+1
        rts
hidden_nmi:
        pha
        lda #1
        sta _udeks_storage_lease_pending
        pla
        rti
        .assert *-hidden_nmi = 8, error, "hidden NMI stub grew"
        .assert __BSS_RUN__ = $e000, lderror, "storage state moved"
        .assert __BSS_SIZE__ <= $180, lderror, "storage snapshots enter C stack"
