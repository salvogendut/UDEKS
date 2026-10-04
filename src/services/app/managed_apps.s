; SPDX-License-Identifier: GPL-3.0-or-later
; Legacy clock/wave callbacks plus independently scheduled banked clients.
        .setcpu "6502"
        .export _udeks_managed_apps_start, _udeks_managed_apps_poll
        .export _udeks_xclock_start, _udeks_xclock_stop
        .export _udeks_xclock_is_running, _udeks_xclock_is_focused
        .export _udeks_xwave_start, _udeks_xwave_stop
        .export _udeks_xwave_is_running, _udeks_xwave_is_focused
        .import _udeks_banked_graphics_poll
MANAGED_LOADER=$f916
XCLOCK=$0200
XWAVE=$1200
TASK_ERROR=$f286
        .segment "BSS"
xclock_loaded: .res 1
xwave_loaded: .res 1
        .segment "MODULERODATA"
xclock_name: .asciiz "xclock"
xwave_name: .asciiz "xwave"
        .segment "CODE"
_udeks_managed_apps_start:
        lda #0
        sta xclock_loaded
        sta xwave_loaded
        rts
_udeks_managed_apps_poll:
        jsr _udeks_banked_graphics_poll
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
        bne slot1_start
        lda #<xclock_name
        ldx #>xclock_name
        jsr MANAGED_LOADER
        bne app_load_error
slot1_loaded:
        jsr XCLOCK
        cmp #0
        bne app_error
        inc xclock_loaded
slot1_start:
        jmp XCLOCK+3
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
        beq app_not_ready
        jmp XCLOCK+9
_udeks_xwave_stop:
        lda xwave_loaded
        beq app_not_ready
        jmp XWAVE+9
app_not_ready: lda #1
        rts
_udeks_xclock_is_running:
        lda xclock_loaded
        beq app_false
        jmp XCLOCK+12
_udeks_xwave_is_running:
        lda xwave_loaded
        beq app_false
        jmp XWAVE+12
_udeks_xclock_is_focused:
        lda xclock_loaded
        beq app_false
        jmp XCLOCK+15
_udeks_xwave_is_focused:
        lda xwave_loaded
        beq app_false
        jmp XWAVE+15
app_false: lda #0
        rts
