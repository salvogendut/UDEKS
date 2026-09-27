; SPDX-License-Identifier: GPL-3.0-or-later
;
; Scheduler segment skeleton delivered into $1C00-$1FFF after crt0. The entry
; continues the boot through the fixed kernel entry vector at $2000; the
; resident kernel reaches the scheduler through the published routines below.

        .setcpu "6502"
        .export _scheduler_entry
        .export _udeks_scheduler_init
        .export _udeks_scheduler_tick

KERNEL_ENTRY = $2000
TASK_GATE_SOURCE = $ce00
TASK_GATE_DESTINATION = $ff05
TASK_GATE_SIZE = $c0

        .segment "SCHEDULER"
_scheduler_entry:
        ; The one-shot tail installer temporarily owns TASKGATE. Its source
        ; at $CE00 remains intact because the installed tail ends below it.
        ; Replace it before any bank-1 task can enter the public gates.
        ldy #$00
install_task_gate:
        lda TASK_GATE_SOURCE,y
        sta TASK_GATE_DESTINATION,y
        iny
        cpy #TASK_GATE_SIZE
        bne install_task_gate
        jmp KERNEL_ENTRY
        .assert _scheduler_entry = $1c00, error, "scheduler entry moved"

scheduler_identity:
        .byte 'S', 'C', 'H', 'D'
        .byte $00, $01                  ; version 0.1
        .byte $00, $00                  ; reserved

_udeks_scheduler_init:
        lda #$00
        rts

_udeks_scheduler_tick:
        lda #$00
        rts

scheduler_end:
        .assert scheduler_end <= $2000, error, "scheduler exceeds its page"
