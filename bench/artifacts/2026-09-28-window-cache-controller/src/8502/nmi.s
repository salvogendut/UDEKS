; SPDX-License-Identifier: GPL-3.0-or-later
; No C, ZP, MMU write or device access in the NMI handler. RTI restores the
; interrupted status; only A is touched and explicitly saved. Events coalesce.
        .setcpu "6502"
        .include "nmi-common.inc"
        .export _udeks_nmi_start, _udeks_nmi_drain
        .export _udeks_nmi_stub_size
        .segment "CODE"
_udeks_nmi_start:
        ; Boot-only, kernel I/O, before publishing input readiness. Disable
        ; inherited CIA2 sources before replacing the native RAM vector.
        lda #$7f
        sta $dd0d
        lda $dd0d
        ldx #nmi_stub_end-nmi_stub-1
install:
        lda nmi_stub,x
        sta UDEKS_NMI_ENTRY,x
        dex
        bpl install
        lda #$00
        sta UDEKS_NMI_PENDING
        sta UDEKS_NMI_DRAINS
        sta UDEKS_NMI_DRAINS+1
        lda #<UDEKS_NMI_ENTRY
        sta $fffa
        lda #>UDEKS_NMI_ENTRY
        sta $fffb
        rts

; Only call after the IRQ trampoline selects kernel I/O and saves registers.
; Never acknowledge CIA2 from a worker-flat lease. Clearing pending before
; device acknowledgement keeps an arriving later edge pending for the next IRQ.
_udeks_nmi_drain:
        lda UDEKS_NMI_PENDING
        beq done
        lda #$00
        sta UDEKS_NMI_PENDING
        lda $dd0d
        inc UDEKS_NMI_DRAINS
        bne done
        inc UDEKS_NMI_DRAINS+1
done:
        rts
nmi_stub:
        UDEKS_NMI_STUB
nmi_stub_end:
_udeks_nmi_stub_size = nmi_stub_end-nmi_stub
        .assert nmi_stub_end-nmi_stub = 8, error, "NMI stub size changed"
        .assert UDEKS_NMI_ENTRY+8 <= $ffed, error, "NMI reaches Z80 bootstrap"
        .assert UDEKS_NMI_PENDING > $fff4, error, "NMI state overlaps bootstrap"
        .assert UDEKS_NMI_DRAINS+2 <= $fffa, error, "NMI state reaches vectors"
