; SPDX-License-Identifier: GPL-3.0-or-later
; Fixed-slot managed images. Slot 1 is exclusively xclock OR xcalc.
        .setcpu "6502"
        .export _udeks_managed_apps_start, _udeks_managed_apps_poll
        .export _udeks_xclock_start, _udeks_xclock_stop
        .export _udeks_xclock_is_running, _udeks_xclock_is_focused
        .export _udeks_xwave_start, _udeks_xwave_stop
        .export _udeks_xwave_is_running, _udeks_xwave_is_focused
        .export _udeks_xcalc_start, _udeks_xcalc_stop, _udeks_xcalc_is_running
MANAGED_LOADER=$f916
XCLOCK=$0200
XWAVE=$1200
TASK_ERROR=$f286
        .segment "BSS"
xclock_loaded: .res 1             ; 0 empty, 1 clock, 2 calculator
xwave_loaded: .res 1
        .segment "MODULERODATA"
xclock_name: .asciiz "xclock"
xwave_name: .asciiz "xwave"
        .segment "RODATA"
xcalc_name: .asciiz "xcalc"
        .segment "CODE"
_udeks_managed_apps_start:
        lda #0
        sta xclock_loaded
        sta xwave_loaded
        rts
_udeks_managed_apps_poll:
        lda xclock_loaded
        beq :+
        jsr XCLOCK+6
        cmp #0
        bne app_error
:
        lda xwave_loaded
        beq app_ok
        jsr XWAVE+6
        cmp #0
        bne app_error
app_ok: lda #0
        rts
app_error: lda #1
        rts
_udeks_xclock_start:
        lda xclock_loaded
        cmp #1
        beq slot1_start
        jsr slot1_available
        bne app_slot_busy
        lda #<xclock_name
        ldx #>xclock_name
        jsr MANAGED_LOADER
        bne app_load_error
        lda #1
        bne slot1_loaded
_udeks_xcalc_start:
        lda xclock_loaded
        cmp #2
        beq slot1_start
        jsr slot1_available
        bne app_slot_busy
        lda #<xcalc_name
        ldx #>xcalc_name
        jsr MANAGED_LOADER
        bne app_load_error
        lda #2
slot1_loaded:
        pha
        jsr XCLOCK
        cmp #0
        beq :+
        pla
        lda #0
        sta xclock_loaded
        jmp app_error
:
        pla
        sta xclock_loaded
slot1_start:
        jmp XCLOCK+3
slot1_available:
        lda xclock_loaded
        beq :+
        jsr XCLOCK+12
        cmp #0
        bne :+
        ; Retire poll callbacks before replacing a stopped image.
        sta xclock_loaded
:
        rts
_udeks_xwave_start:
        lda xwave_loaded
        bne wave_loaded
        lda #<xwave_name
        ldx #>xwave_name
        jsr MANAGED_LOADER
        bne app_load_error
        jsr XWAVE
        cmp #0
        bne app_error
        inc xwave_loaded
wave_loaded:
        jmp XWAVE+3
app_load_error:
        cmp #3
        beq app_slot_busy
        lda TASK_ERROR
        cmp #$0b
        beq app_not_found
        cmp #$0d
        beq app_disk_error
        lda #5
        rts
app_slot_busy: lda #4
        rts
app_not_found: lda #3
        rts
app_disk_error: lda #6
        rts
_udeks_xclock_stop:
        lda xclock_loaded
        cmp #1
        bne app_not_ready
        jmp XCLOCK+9
_udeks_xcalc_stop:
        lda xclock_loaded
        cmp #2
        bne app_not_ready
        jmp XCLOCK+9
_udeks_xwave_stop:
        lda xwave_loaded
        beq app_not_ready
        jmp XWAVE+9
app_not_ready: lda #1
        rts
_udeks_xclock_is_running:
        lda xclock_loaded
        cmp #1
        bne app_false
        jmp XCLOCK+12
_udeks_xcalc_is_running:
        lda xclock_loaded
        cmp #2
        bne app_false
        jmp XCLOCK+12
_udeks_xwave_is_running:
        lda xwave_loaded
        beq app_false
        jmp XWAVE+12
_udeks_xclock_is_focused:
        lda xclock_loaded
        cmp #1
        bne app_false
        jmp XCLOCK+15
_udeks_xwave_is_focused:
        lda xwave_loaded
        beq app_false
        jmp XWAVE+15
app_false: lda #0
        rts
