; SPDX-License-Identifier: GPL-3.0-or-later
;
; Production-shaped Tasking 0.1 common-RAM tail prototype. It preserves the
; published $FF10/$FF13/$FF16 entries and fits the exact $FF05-$FFC4 legacy
; reservation. It is deliberately not installed yet: the resident callbacks
; and task entry wrapper must land before it can replace task_bank_gateway.s.

        .setcpu "6502"
        .segment "TASKGATE"

        .export _udeks_task_switch_tail
        .export _udeks_task_switch_reset_gate
        .export _udeks_task_switch_poll_gate
        .export _udeks_task_switch_request_gate

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_FLAT     = $ff04
MMU_PAGE0_PAGE          = $d507
MMU_PAGE0_BANK          = $d508
MMU_PAGE1_PAGE          = $d509
MMU_PAGE1_BANK          = $d50a

SCHEDULER_RESET         = $cdd0
SCHEDULER_SELECT        = $cdd3
TASK_REQUEST_DISPATCH   = $cf30

TASK_NOT_READY          = $01

_udeks_task_switch_tail:
        .byte 'U', 'T', 'G', '2'
        .byte $00, $03
tail_state:
        .byte $00
tail_last_result:
        .byte $00
tail_switches_low:
        .byte $00
tail_switches_high:
        .byte $00
        .byte $00

        .assert * = $ff10, error, "task-switch reset vector moved"
_udeks_task_switch_reset_gate:
        jmp tail_reset
_udeks_task_switch_poll_gate:
        jmp tail_poll
_udeks_task_switch_request_gate:
        jmp tail_request

; The bank-0 scheduler initializes the context record and relocated pages.
tail_reset:
        jmp SCHEDULER_RESET

; Entered from the resident service poll with the kernel hardware stack and
; kernel page-zero/page-one mapping active. SCHEDULER_SELECT returns zero when
; no task is runnable; otherwise it fills the common context record below.
tail_poll:
        php
        sei
        tsx
        stx kernel_sp
        jsr SCHEDULER_SELECT
        bne tail_restore
tail_no_task:
        ldx kernel_sp
        txs
        plp
        lda #TASK_NOT_READY
        ldx #$00
        rts

; $FF16 is called with a task's relocated page zero/page one active. Capture
; the live return frame before selecting the kernel mapping. The resident
; dispatcher returns carry clear for a synchronous response and carry set when
; the task must remain suspended. On a synchronous response A/X become the
; task-visible call result; the original Y/P and live stack are restored.
tail_request:
        sta context_a
        stx context_x
        sty context_y
        php
        sei
        pla
        sta context_p
        tsx
        stx context_sp
        lda #<tail_request_resume
        sta context_pc
        lda #>tail_request_resume
        sta context_pc+1

        lda #$00
        sta MMU_LCR_KERNEL_IO
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE
        ldx kernel_sp
        txs
        jsr TASK_REQUEST_DISPATCH
        bcs tail_suspend
        sta context_a
        stx context_x
        jmp tail_restore

tail_suspend:
        inc tail_switches_low
        bne :+
        inc tail_switches_high
:
        ldx kernel_sp
        txs
        plp
        lda #$00
        ldx #$00
        rts

; The context record is populated only by the resident scheduler or by the
; request capture above. MMU page registers are changed while kernel I/O is
; still visible; the final LCR write selects the task's bank-1 address space.
tail_restore:
        lda context_page0_bank
        sta MMU_PAGE0_BANK
        lda context_page0_page
        sta MMU_PAGE0_PAGE
        lda context_page1_bank
        sta MMU_PAGE1_BANK
        lda context_page1_page
        sta MMU_PAGE1_PAGE
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        ldx context_sp
        txs
        lda context_p
        pha
        lda context_a
        ldx context_x
        ldy context_y
        plp
        jmp (context_pc)

tail_request_resume:
        rts

; Common scratch record. Per-task storage remains scheduler-owned in bank 0;
; only the selected or outgoing task occupies this handoff record.
kernel_sp:              .byte $00
context_a:              .byte $00
context_x:              .byte $00
context_y:              .byte $00
context_p:              .byte $00
context_sp:             .byte $00
context_pc:             .word $0000
context_page0_page:     .byte $00
context_page0_bank:     .byte $00
context_page1_page:     .byte $00
context_page1_bank:     .byte $00

task_switch_tail_end:
        .assert task_switch_tail_end <= $ffc5, error, "task-switch tail exceeds $FF05-$FFC4"
