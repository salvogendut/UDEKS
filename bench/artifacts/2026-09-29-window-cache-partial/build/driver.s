; SPDX-License-Identifier: GPL-3.0-or-later
; Diagnostic-only uploader, IRQ, runtime/flag/stack oracle and guard scanner.
; None of this code is counted as a production resident binding.
        .setcpu "6502"
        .include "layout.inc"
        .importzp ptr1, ptr2
        .import _cache_accept_poll, _cache_step, _cache_accept_state
        .export _runtime_accept, _runtime_accept_count, _runtime_step
        .import _udeks_nmi_drain
        .import _private_cache_policy_call
        .export _runtime_install, _runtime_call
        .export _runtime_irq_start, _runtime_irq_stop, _runtime_check_memory
        .export _runtime_irq_count, _runtime_irq_bad, _runtime_zp_bad
        .export _runtime_hw_bad, _runtime_flags_bad, _runtime_sw_bad
        .export _runtime_guard_bad, _runtime_ush_bad, _runtime_low_water
        .export _runtime_call_count
        .export _runtime_seen_flags
        .segment "BSS"
_runtime_irq_count: .res 4
_runtime_call_count: .res 2
_runtime_accept_count: .res 2
_runtime_irq_bad: .res 1
_runtime_zp_bad: .res 1
_runtime_hw_bad: .res 1
_runtime_flags_bad: .res 1
_runtime_sw_bad: .res 1
_runtime_guard_bad: .res 1
_runtime_ush_bad: .res 1
_runtime_low_water: .res 1
_runtime_seen_flags: .res 1
saved_zp: .res ZP_BYTES
saved_hw_sp: .res 1
saved_flags: .res 1
saved_result: .res 1
        .segment "CODE"
_runtime_install:
        sei
        lda #$3e
        sta $d501
        lda #$7f
        sta $d504
        lda #<module_image
        sta ptr1
        lda #>module_image
        sta ptr1+1
        lda #<$4200
        sta ptr2
        lda #>$4200
        sta ptr2+1
        ldx #upload_end-upload-1
install_upload:
        lda upload,x
        sta RUN,x
        dex
        bpl install_upload
        jsr RUN
        ldx #$00
install_seed:
        lda seed,x
        sta RUN,x
        inx
        cpx #seed_end-seed
        bcc install_seed
        jsr RUN
        lda #$ff
        sta _runtime_low_water
        lda #$a5
        sta $0100               ; bottom of actually mapped hardware stack
        sta $e700               ; bottom of live caller software-stack lease
        ldx #$0f
        lda #$5a
caller_top:
        sta $eff0,x             ; live caller stack is strictly below its top
        dex
        bpl caller_top
        rts
upload:
        ldx #$11                ; private controller envelope
        ldy #$00
upload_byte:
        lda #$00
        sta KERNEL
        lda (ptr1),y
        pha
        lda #$00
        sta WORKER
        pla
        sta (ptr2),y
        iny
        bne upload_byte
        inc ptr1+1
        inc ptr2+1
        dex
        bne upload_byte
        lda #$00
        sta KERNEL
        rts
upload_end:
seed:
        lda #$00
        sta WORKER
        ldx #$00
        lda #$a5
seed_stack:
        sta STACK_BOTTOM,x
        inx
        cpx #$f0
        bcc seed_stack
        lda #$5a
        ; Explicit upper/private-state guards, no assumed zero bytes.
        ldx #$0f
guard_top:
        sta STACK_TOP,x
        dex
        bpl guard_top
        ldx #$15
guard_state:
        sta FLOW+4,x
        dex
        bpl guard_state
        sta $41ff
        ldx #$19
        lda #$6d
private_markers:
        sta LEASE,x
        dex
        bpl private_markers
        lda #$a5
        sta CACHE_LIMIT
        lda #<$e700
        sta ptr2
        lda #>$e700
        sta ptr2+1
        ldx #$09
        ldy #$00
seed_ush:
        tya
        eor #$69
        sta (ptr2),y
        iny
        bne seed_ush
        inc ptr2+1
        dex
        bne seed_ush
        lda #$00
        sta KERNEL
        rts
seed_end:
        .assert seed_end-seed < $80, error, "diagnostic seed copy exceeds loop"

_runtime_call:
        tsx
        stx saved_hw_sp
        ldx #ZP_BYTES-1
snapshot_zp:
        lda ZP_FIRST,x
        sta saved_zp,x
        dex
        bpl snapshot_zp
        lda _runtime_call_count
        and #$03
        tax
        lda flag_bits,x
        ora _runtime_seen_flags
        sta _runtime_seen_flags
        lda flag_modes,x
        sta saved_flags
        pha
        plp
        jsr _private_cache_policy_call
        sta saved_result
        php
        pla
        and #$0c
        cmp saved_flags
        beq flags_ok
        lda #$01
        sta _runtime_flags_bad
flags_ok:
        cld
        tsx
        cpx saved_hw_sp
        beq hw_ok
        lda #$01
        sta _runtime_hw_bad
hw_ok:
        ldx #ZP_BYTES-1
compare_zp:
        lda ZP_FIRST,x
        cmp saved_zp,x
        beq zp_byte_ok
        lda #$01
        sta _runtime_zp_bad
zp_byte_ok:
        ; Repair after observing, so a real restore bug can be decoded rather
        ; than crashing the diagnostic C caller. This is NOT in the binding.
        lda saved_zp,x
        sta ZP_FIRST,x
        dex
        bpl compare_zp
        lda _cache_accept_state
        cmp #$80
        bne sw_ok
        lda RETURN_SP
        cmp #<STACK_TOP
        bne sw_bad
        lda RETURN_SP+1
        cmp #>STACK_TOP
        beq sw_ok
sw_bad:
        lda #$01
        sta _runtime_sw_bad
sw_ok:
        lda $ff00
        cmp #$3e
        beq map_ok
        lda #$01
        sta _runtime_irq_bad
map_ok:
        inc _runtime_call_count
        bne counted
        inc _runtime_call_count+1
counted:
        cli
        lda saved_result
        ldx #$00
        rts
_runtime_accept:
        tsx
        stx saved_hw_sp
        ldx #ZP_BYTES-1
snapshot_zp_accept:
        lda ZP_FIRST,x
        sta saved_zp,x
        dex
        bpl snapshot_zp_accept
        lda _runtime_accept_count
        and #$03
        tax
        lda flag_bits,x
        ora _runtime_seen_flags
        sta _runtime_seen_flags
        lda flag_modes,x
        sta saved_flags
        pha
        plp
        jsr _cache_accept_poll
        sta saved_result
        php
        pla
        and #$0c
        cmp saved_flags
        beq flags_ok_accept
        lda #$01
        sta _runtime_flags_bad
flags_ok_accept:
        cld
        tsx
        cpx saved_hw_sp
        beq hw_ok_accept
        lda #$01
        sta _runtime_hw_bad
hw_ok_accept:
        ldx #ZP_BYTES-1
compare_zp_accept:
        lda ZP_FIRST,x
        cmp saved_zp,x
        beq zp_byte_ok_accept
        lda #$01
        sta _runtime_zp_bad
zp_byte_ok_accept:
        ; Repair after observing, so a real restore bug can be decoded rather
        ; than crashing the diagnostic C caller. This is NOT in the binding.
        lda saved_zp,x
        sta ZP_FIRST,x
        dex
        bpl compare_zp_accept

        lda $ff00
        cmp #$3e
        beq map_ok_accept
        lda #$01
        sta _runtime_irq_bad
map_ok_accept:
        inc _runtime_accept_count
        bne counted_accept
        inc _runtime_accept_count+1
counted_accept:
        cli
        lda saved_result
        ldx #$00
        rts
_runtime_step:
        tsx
        stx saved_hw_sp
        ldx #ZP_BYTES-1
snapshot_zp_step:
        lda ZP_FIRST,x
        sta saved_zp,x
        dex
        bpl snapshot_zp_step
        lda _runtime_call_count
        and #$03
        tax
        lda flag_bits,x
        ora _runtime_seen_flags
        sta _runtime_seen_flags
        lda flag_modes,x
        sta saved_flags
        pha
        plp
        jsr _cache_step
        sta saved_result
        php
        pla
        and #$0c
        cmp saved_flags
        beq flags_ok_step
        lda #$01
        sta _runtime_flags_bad
flags_ok_step:
        cld
        tsx
        cpx saved_hw_sp
        beq hw_ok_step
        lda #$01
        sta _runtime_hw_bad
hw_ok_step:
        ldx #ZP_BYTES-1
compare_zp_step:
        lda ZP_FIRST,x
        cmp saved_zp,x
        beq zp_byte_ok_step
        lda #$01
        sta _runtime_zp_bad
zp_byte_ok_step:
        ; Repair after observing, so a real restore bug can be decoded rather
        ; than crashing the diagnostic C caller. This is NOT in the binding.
        lda saved_zp,x
        sta ZP_FIRST,x
        dex
        bpl compare_zp_step
        lda RETURN_SP
        cmp #<STACK_TOP
        bne sw_bad_step
        lda RETURN_SP+1
        cmp #>STACK_TOP
        beq sw_ok_step
sw_bad_step:
        lda #$01
        sta _runtime_sw_bad
sw_ok_step:
        lda $ff00
        cmp #$3e
        beq map_ok_step
        lda #$01
        sta _runtime_irq_bad
map_ok_step:
        inc _runtime_call_count
        bne counted_step
        inc _runtime_call_count+1
counted_step:
        cli
        lda saved_result
        ldx #$00
        rts
flag_modes: .byte $00,$04,$08,$0c
flag_bits: .byte $01,$02,$04,$08

_runtime_check_memory:
        php
        sei
        cld
        ldx #$00
install_scan:
        lda scan,x
        sta RUN,x
        inx
        cpx #scan_end-scan
        bcc install_scan
        lda #$00
        sta $f78a
        sta $f78b
        lda #$ff
        sta $f78c
        jsr RUN
        lda $f78a
        beq guards_ok
        sta _runtime_guard_bad
guards_ok:
        lda $0100
        cmp #$a5
        beq bottom_ok
        lda #$01
        sta _runtime_hw_bad
bottom_ok:
        lda $e700
        cmp #$a5
        bne caller_guard_bad
        ldx #$0f
caller_guard:
        lda $eff0,x
        cmp #$5a
        bne caller_guard_bad
        dex
        bpl caller_guard
        jmp caller_guard_ok
caller_guard_bad:
        lda #$01
        sta _runtime_guard_bad
caller_guard_ok:
        lda $f78b
        beq ush_ok
        sta _runtime_ush_bad
ush_ok:
        lda $f78c
        cmp _runtime_low_water
        bcs water_ok
        sta _runtime_low_water
water_ok:
        plp
        rts
scan:
        lda #$00
        sta WORKER
        ldx #$19
snapshot_private:
        lda LEASE,x
        sta STAGE,x
        dex
        bpl snapshot_private
        lda #$00
        sta WORKER
        ldx #$00
scan_low:
        lda STACK_BOTTOM,x
        cmp #$a5
        bne guard_bad
        inx
        cpx #$40
        bcc scan_low
        ldx #$0f
scan_high:
        lda STACK_TOP,x
        cmp #$5a
        bne guard_bad
        dex
        bpl scan_high
        ldx #$15
scan_state:
        lda FLOW+4,x
        cmp #$5a
        bne guard_bad
        dex
        bpl scan_state
        lda $41ff
        cmp #$5a
        bne guard_bad
        lda CACHE_LIMIT
        cmp #$a5
        beq measure_water
guard_bad:
        inc $f78a
measure_water:
        ldx #$40
water:
        lda STACK_BOTTOM,x
        cmp #$a5
        bne found_water
        inx
        cpx #$f0
        bcc water
found_water:
        stx $f78c
        lda #<$e700
        sta ptr2
        lda #>$e700
        sta ptr2+1
        ldx #$09
        ldy #$00
scan_ush:
        tya
        eor #$69
        cmp (ptr2),y
        beq ush_byte_ok
        lda #$01
        sta $f78b
ush_byte_ok:
        iny
        bne scan_ush
        inc ptr2+1
        dex
        bne scan_ush
        lda #$00
        sta KERNEL
        rts
scan_end:
        .assert scan_end-scan < $100, error, "diagnostic scan exceeds loop"
        .assert RUN+scan_end-scan < $ff80, error, "scan reaches diagnostic IRQ"

_runtime_irq_start:
        sei
        ldx #irq_end-irq-1
install_irq:
        lda irq,x
        sta $ff80,x
        dex
        bpl install_irq
        lda #<$ff80
        sta $fffe
        lda #>$ff80
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
_runtime_irq_stop:
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
        sta KERNEL
        cmp #$3e
        beq mapped
        lda #$01
        sta _runtime_irq_bad
mapped:
        jsr _udeks_nmi_drain
        lda $dc0d
        inc _runtime_irq_count
        bne irq_done
        inc _runtime_irq_count+1
        bne irq_done
        inc _runtime_irq_count+2
        bne irq_done
        inc _runtime_irq_count+3
irq_done:
        pla
        sta $ff00
        pla
        tay
        pla
        tax
        pla
        rti
irq_end:
        .assert $ff80+irq_end-irq < $fffa, error, "IRQ reaches parameters"

        .segment "RODATA"
module_image:
        .incbin "build/bench/window-cache-partial/acceptance/module-envelope.bin"
module_image_end:
        .assert module_image_end-module_image = $1100, error, "diagnostic upload length changed"

.segment "CODE"
.export _cache_copy_fault_probe
_cache_copy_fault_probe:
        lda #$06
        sta $f6c1
        lda #$53
        sta $f6a4
        rts
