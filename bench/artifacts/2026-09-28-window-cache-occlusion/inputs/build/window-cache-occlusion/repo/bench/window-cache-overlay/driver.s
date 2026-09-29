; SPDX-License-Identifier: GPL-3.0-or-later
; Diagnostic installer/IRQ harness only. Production must deliver CORE without
; retaining an embedded bank-0 copy. No ROM or external services used.
        .setcpu "6502"
        .include "layout.inc"
        .import _vic_cache_row_candidate
        .export _overlay_install, _overlay_row, _overlay_irq_start
        .export _overlay_irq_stop, _overlay_irq_count, _overlay_irq_bad
        .export _overlay_flags_probe, _overlay_flag_failure
        .export _overlay_guards
        .export _overlay_stack_failure
        .segment "BSS"
_overlay_irq_count: .res 2
_overlay_irq_bad: .res 1
_overlay_flag_failure: .res 1
_overlay_stack_failure: .res 1
saved_sp: .res 1
        .segment "CODE"
_overlay_install:
        ldx #$00
install:
        lda gateway_image,x
        sta RUN,x
        inx
        cpx #gateway_image_end-gateway_image
        bcc install
        ldx #upload_end-upload-1
install_upload:
        lda upload,x
        sta $f740,x
        dex
        bpl install_upload
        jsr $f740
        lda #$00
        sta $f3ed
        rts
upload:
        ldx #$00
upload_loop:
        lda #$00
        sta KERNEL
        lda core_image,x
        pha
        lda #$00
        sta WORKER
        pla
        sta CORE,x
        inx
        cpx #core_image_end-core_image
        bcc upload_loop
        lda #$5a
        sta $43ff
        lda #$a5
        sta $5c00
        sta $4428
        sta $5580
        lda #$00
        sta KERNEL
        rts
upload_end:
        .assert $f740+upload_end-upload <= PARAM, error, "diagnostic upload reaches parameters"
_overlay_row:
        tsx
        stx saved_sp
        jsr _vic_cache_row_candidate
        tsx
        cpx saved_sp
        beq stack_ok
        lda #$01
        sta _overlay_stack_failure
stack_ok:
        rts
_overlay_guards:
        ldx #guards_end-guards-1
install_guards:
        lda guards,x
        sta $f740,x
        dex
        bpl install_guards
        jmp $f740
guards:
        lda PARAM+10
        sta $f740+(peek_guard-guards)+1
        lda PARAM+11
        sta $f740+(peek_guard-guards)+2
        lda #$00
        sta WORKER
        lda $43ff
        pha
        lda $5c00
        pha
peek_guard:
        lda $ffff
        pha
        lda #$00
        sta KERNEL
        pla
        sta $7fd3
        pla
        sta $7fd1
        pla
        sta $7fd0
        rts
guards_end:
        .assert $f740+guards_end-guards <= PARAM, error, "guard upload reaches parameters"
_overlay_irq_start:
        sei
        ldx #irq_end-irq-1
install_irq:
        lda irq,x
        sta $f740,x
        dex
        bpl install_irq
        lda #<$f740
        sta $fffe
        lda #>$f740
        sta $ffff
        lda #$7f
        sta $dc0d
        lda $dc0d
        lda #$81
        sta $dc0d
        lda #$00
        sta $dc04
        lda #$02
        sta $dc05
        lda #$11
        sta $dc0e
        cli
        rts
_overlay_irq_stop:
        sei
        lda #$00
        sta $dc0e
        lda #$7f
        sta $dc0d
        lda $dc0d
        rts
irq:
        pha
        txa
        pha
        tya
        pha
        cld
        lda $ff00
        pha
        sta KERNEL              ; any store invokes the preconfigured profile
        cmp #$3e
        beq mapped
        lda #$01
        sta _overlay_irq_bad
mapped:
        lda $dc0d
        inc _overlay_irq_count
        bne irq_done
        inc _overlay_irq_count+1
irq_done:
        pla
        sta $ff00               ; return to the actual interrupted map
        pla
        tay
        pla
        tax
        pla
        rti
irq_end:
        .assert $f740+irq_end-irq <= PARAM, error, "diagnostic IRQ reaches parameters"
; Valid capture parameters are supplied by C. Check all four I/D states.
_overlay_flags_probe:
        php
        sei
        cld
        jsr _vic_cache_row_candidate
        php
        pla
        and #$0c
        cmp #$04
        bne flag_failed
        sed
        jsr _vic_cache_row_candidate
        php
        pla
        and #$0c
        cmp #$0c
        bne flag_failed
        cli
        jsr _vic_cache_row_candidate
        php
        pla
        and #$0c
        cmp #$08
        bne flag_failed
        cld
        jsr _vic_cache_row_candidate
        php
        pla
        and #$0c
        beq flags_done
flag_failed:
        lda #$01
        sta _overlay_flag_failure
flags_done:
        plp
        rts
gateway_image:
        .incbin "build/bench/window-cache-overlay/gateway.bin"
gateway_image_end:
core_image:
        .incbin "build/bench/window-cache-overlay/core.bin"
core_image_end:
        .assert core_image_end-core_image < $100, error, "diagnostic uploader requires one page"
