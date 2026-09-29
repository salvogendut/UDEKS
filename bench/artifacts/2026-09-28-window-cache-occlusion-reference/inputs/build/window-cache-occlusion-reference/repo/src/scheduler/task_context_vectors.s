; SPDX-License-Identifier: GPL-3.0-or-later
;
; Fixed scheduler-page callbacks used by the common-RAM switch tail. This
; object is deliberately linked last in SCHEDULER.

        .setcpu "6502"
        .segment "SCHEDULER"

        .import _udeks_task_context_reset
        .import _udeks_task_context_select

        .assert * = $1ffa, error, "task-context vectors moved"
        jmp _udeks_task_context_reset
        jmp _udeks_task_context_select
        .assert * = $2000, error, "task-context vectors exceed scheduler page"
