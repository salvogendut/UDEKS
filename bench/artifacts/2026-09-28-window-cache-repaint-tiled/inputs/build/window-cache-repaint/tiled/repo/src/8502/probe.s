; SPDX-License-Identifier: GPL-3.0-or-later
;
; Bounded machine-probe mechanisms used by the C capability service.

        .setcpu "6502"
        .export _udeks_probe_video_standard
        .export _udeks_probe_vdc_revision
        .export _udeks_probe_reu
        .export _udeks_probe_georam

VIC_CONTROL_1           = $d011
VIC_RASTER              = $d012
VDC_STATUS              = $d600
REU_ADDRESS_LOW         = $df04
GEORAM_WINDOW           = $de00
GEORAM_PAGE             = $dffe
GEORAM_BANK             = $dfff

VIDEO_UNKNOWN           = $00
VIDEO_PAL               = $01
VIDEO_NTSC              = $02

        ; The probe is staged in the VIC shadow and copied over the dead
        ; boot-sector page at $0B00, so its scratch bytes travel with it.
        .segment "PROBECODE"
probe_saved_reu:
        .byte $00
probe_saved_geo_page:
        .byte $00
probe_saved_geo_bank:
        .byte $00
probe_saved_geo_data:
        .byte $00

        .segment "PROBECODE"

; PAL reaches raster $120; NTSC wraps near $106. Each phase has a complete
; 16-bit polling bound so a missing or frozen VIC returns UNKNOWN.
_udeks_probe_video_standard:
        ldx #$00
        ldy #$00
wait_low:
        bit VIC_CONTROL_1
        bpl low_seen
        inx
        bne wait_low
        iny
        bne wait_low
        lda #VIDEO_UNKNOWN
        rts

low_seen:
        ldx #$00
        ldy #$00
wait_high:
        bit VIC_CONTROL_1
        bmi high_seen
        inx
        bne wait_high
        iny
        bne wait_high
        lda #VIDEO_UNKNOWN
        rts

high_seen:
        ldx #$00
        ldy #$00
scan_high_rasters:
        bit VIC_CONTROL_1
        bpl ntsc_seen
        lda VIC_RASTER
        cmp #$20
        bcs pal_seen
        inx
        bne scan_high_rasters
        iny
        bne scan_high_rasters
        lda #VIDEO_UNKNOWN
        rts

ntsc_seen:
        lda #VIDEO_NTSC
        rts
pal_seen:
        lda #VIDEO_PAL
        rts

; VDC status bits 0..2 are the silicon revision. $FF denotes timeout.
_udeks_probe_vdc_revision:
        ldx #$00
        ldy #$00
vdc_wait:
        lda VDC_STATUS
        bmi vdc_ready
        inx
        bne vdc_wait
        iny
        bne vdc_wait
        lda #$ff
        rts
vdc_ready:
        and #$07
        rts

; Follow the cc65 REU driver's non-DMA presence test: two values must echo
; through expansion-address register $DF04. Restore the previous value.
_udeks_probe_reu:
        lda REU_ADDRESS_LOW
        sta probe_saved_reu
        lda #$55
        sta REU_ADDRESS_LOW
        cmp REU_ADDRESS_LOW
        bne reu_absent
        lda #$aa
        sta REU_ADDRESS_LOW
        cmp REU_ADDRESS_LOW
        bne reu_absent
        lda probe_saved_reu
        sta REU_ADDRESS_LOW
        lda #$01
        rts
reu_absent:
        lda probe_saved_reu
        sta REU_ADDRESS_LOW
        lda #$00
        rts

; Probe one GeoRAM byte through its documented $DE00 window while saving and
; restoring the selected page, bank, and byte. This is intentionally run only
; during single-owner startup before cartridge resources can be leased.
_udeks_probe_georam:
        lda GEORAM_PAGE
        sta probe_saved_geo_page
        lda GEORAM_BANK
        sta probe_saved_geo_bank
        lda #$00
        sta GEORAM_PAGE
        sta GEORAM_BANK
        lda GEORAM_WINDOW
        sta probe_saved_geo_data
        lda #$55
        sta GEORAM_WINDOW
        cmp GEORAM_WINDOW
        bne georam_absent
        lda #$aa
        sta GEORAM_WINDOW
        cmp GEORAM_WINDOW
        bne georam_absent
        lda #$01
        bne georam_restore
georam_absent:
        lda #$00
georam_restore:
        pha
        lda probe_saved_geo_data
        sta GEORAM_WINDOW
        lda probe_saved_geo_page
        sta GEORAM_PAGE
        lda probe_saved_geo_bank
        sta GEORAM_BANK
        pla
        rts
