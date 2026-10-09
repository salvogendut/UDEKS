; SPDX-License-Identifier: GPL-3.0-or-later
;
; Stable 8502 user/kernel call gate. Each vector is one absolute JMP so a
; caller may JSR the published address and receive the implementation's RTS.

        .setcpu "6502"
        .segment "SYSCALLS"

        .export _udeks_syscall_table
        .export _udeks_syscall_write_byte_gate
        .export _udeks_syscall_write_gate
        .export _udeks_syscall_task_request_gate
        .export _udeks_syscall_clock_set_gate
        .import _udeks_stream_write_byte
        .import _udeks_stream_write
        .import _udeks_line_editor_read
        .import _udeks_terminal_input_access
        .import _udeks_root_terminal_write_request
        .import _udeks_root_terminal_prompt
        .import _udeks_shell_command_line
        .import _udeks_shell_foreground_job
        .import _udeks_service_control_request
        .import _udeks_task_worker_request
        .import _udeks_banked_graphics_request, _udeks_banked_graphics_installed
        .import _udeks_bootfs_finish_error, _udeks_bootfs_finish_ok
        .import _udeks_bootfs_request
        .ifdef UDEKS_DISK_TIME
        .import _udeks_time_slot_set
        .include "../services/module/request.inc"
        .export _udeks_time_slot_request
clock_set_runtime = _udeks_time_slot_set
        .else
        .export _udeks_time_sync_ti
        .endif
        .import pusha
        .import pushax
        .importzp tmp1, ptr1

TREQ_BASE       = $f359
TREQ_STATE      = TREQ_BASE+$06
TREQ_OPERATION  = TREQ_BASE+$07
TREQ_DESCRIPTOR = TREQ_BASE+$09
TREQ_COUNT      = TREQ_BASE+$0a
TREQ_RESULT     = TREQ_BASE+$0b
TREQ_ERROR      = TREQ_BASE+$0c
TREQ_FLAGS      = TREQ_BASE+$0d
TREQ_PAYLOAD    = TREQ_BASE+$0e
TASK_COMMAND    = $f3a0
SHELL_PENDING_EXEC = $f187

TREQ_REQUEST    = $01
TREQ_COMPLETE   = $02
TREQ_STATE_ERROR = $80
TREQ_OP_READ    = $01
TREQ_OP_WRITE   = $02
TREQ_OP_EXEC    = $03
TREQ_OP_WAIT    = $04
TREQ_OP_PROMPT  = $05

ERR_EIO         = $05
ERR_EBADF       = $09
ERR_EAGAIN      = $0b
ERR_EINVAL      = $16
ERR_ENOSYS      = $26
ERR_EPROTO      = $47

_udeks_syscall_table:
        .byte 'U', 'S', 'Y', 'S'
        .byte $00, $03
        .byte $04, $10
        .res 8, $00

        ; $CF10: A=descriptor, X=byte. Marshal to the resident C service.
_udeks_syscall_write_byte_gate:
        stx tmp1
        jsr pusha
        lda tmp1
        ldx #$00
        jmp _udeks_stream_write_byte
        .res 4, $ea

        ; $CF20: A=descriptor, X=pointer low, Y=pointer high.
        ; ptr1 is part of the kernel's reserved runtime zero page.
_udeks_syscall_write_gate:
        stx ptr1
        sty ptr1+1
        jsr pusha
        lda ptr1
        ldx ptr1+1
        jmp _udeks_stream_write
        .res 2, $ea

        ; $CF30: dispatch the common-RAM bank-task request record. The common
        ; gate has already selected the kernel map and restored resident ZP.
_udeks_syscall_task_request_gate:
        jmp task_request_runtime
        .ifdef UDEKS_DISK_TIME
        time_module_abort_body
        .res 16-(*-_udeks_syscall_task_request_gate), $ea
        .else
        .res 13, $ea
        .endif

        ; $CF40: A=hour, X=minute, Y=second. Set the shared service clock and
        ; CIA1 TOD; the time service mirrors it into BASIC's TI counter.
_udeks_syscall_clock_set_gate:
        jmp clock_set_runtime
        .ifdef UDEKS_DISK_TIME
time_module_reply:
        time_module_reply_body
        .res 16-(*-_udeks_syscall_clock_set_gate), $ea
        .else
        .res 13, $ea
        .endif

        .assert _udeks_syscall_table = $cf00, error, "syscall table moved"
        .assert _udeks_syscall_write_byte_gate = $cf10, error, "write-byte gate moved"
        .assert _udeks_syscall_write_gate = $cf20, error, "write gate moved"
        .assert _udeks_syscall_task_request_gate = $cf30, error, "task request gate moved"
        .assert _udeks_syscall_clock_set_gate = $cf40, error, "clock-set gate moved"
        .assert * = $cf50, error, "base syscall vectors exceed reserved slots"

        .include "app_gateway.s"

        .segment "CODE"
        .ifdef UDEKS_DISK_TIME
_udeks_time_slot_request:
        time_module_request_body
        .endif
task_extended_request:
        lda TREQ_OPERATION
        cmp #24
        bne :+
        jsr _udeks_task_worker_request
        cmp #0
        bne worker_error
        lda #3
        jmp _udeks_bootfs_finish_ok
worker_error:
        jmp _udeks_bootfs_finish_error
:
        cmp #23
        bne :+
        lda _udeks_banked_graphics_installed
        bne graphics_dispatch
        lda #38
        jmp _udeks_bootfs_finish_error
graphics_dispatch:
        jsr _udeks_banked_graphics_request
        lda #0
        tax
        clc
        rts
:
        cmp #20
        bne :+
        jsr _udeks_service_control_request
        ; C set means suspend to the native scheduler, not a C return flag.
        ; Control only enqueues work and must always return synchronously.
        lda #0
        ldx #0
        clc
        rts
:
        jmp $c880

task_exec_pending:
        ; Text is now private; release the shared input/reply mailbox.
        lda #$00
        sta TASK_COMMAND
        lda #$01
        sta SHELL_PENDING_EXEC
        jmp task_finish_ok

        .ifndef UDEKS_DISK_TIME
        .include "../services/time/clock_set.inc"
        .endif

        ; The bounded implementation resides in reclaimed common boot RAM.
        ; Stage 1 installs this separately after its own common gateway exits.
        .segment "TASKREQUEST"
task_request_runtime:
        ldx #$04
task_validate_signature:
        lda TREQ_BASE,x
        cmp task_signature,x
        bne task_protocol_trampoline
        dex
        bpl task_validate_signature
        lda TREQ_BASE+$05
        cmp #$15                    ; accept UTRQ 0.0..0.20 (packed bitmaps)
        bcs task_protocol_trampoline
        lda TREQ_STATE
        cmp #TREQ_REQUEST
        bne task_protocol_trampoline
        ; ABI 0.3 lifecycle/0.4 POLL operations are owned by the installed fallback
        ; service; this compatibility gate deliberately does not decode them.
        lda TREQ_OPERATION
        cmp #$0a
        bcs task_request_fallback
        lda TREQ_FLAGS
        bne task_protocol_trampoline
task_dispatch_operation:
        lda TREQ_OPERATION
        cmp #TREQ_OP_READ
        beq task_read
        cmp #TREQ_OP_WRITE
        beq task_write
        cmp #TREQ_OP_EXEC
        beq task_exec
        cmp #TREQ_OP_WAIT
        bne task_check_prompt
        jmp task_wait
task_check_prompt:
        cmp #TREQ_OP_PROMPT
        bne task_request_fallback
        jmp task_prompt
task_request_fallback:
        jmp task_extended_request  ; service control, storage, bootfs/lifecycle
task_protocol_trampoline:
        jmp task_protocol_error

task_read:
        lda TREQ_DESCRIPTOR
        beq task_read_descriptor_ok
        jmp $c880                   ; storage descriptor or bootfs EBADF
task_read_descriptor_ok:
        lda TREQ_COUNT
        cmp #$19
        bcc task_read_count_ok
        jmp task_invalid
task_read_count_ok:
        jsr _udeks_terminal_input_access
        bne task_input_denied
        lda #<TREQ_PAYLOAD
        ldx #>TREQ_PAYLOAD
        jsr pushax
        lda TREQ_COUNT
        jsr _udeks_line_editor_read
        cmp #$ff
        beq task_would_block
        jmp task_finish_ok

task_write:
        lda TREQ_DESCRIPTOR
        cmp #$01
        beq task_write_valid
        cmp #$02
        beq task_write_valid
        jmp $c880                   ; file WRITE, version/mode/owner in service
task_write_valid:
        lda TREQ_COUNT
        cmp #$19
        bcs task_invalid
        jsr _udeks_root_terminal_write_request
        lda TREQ_COUNT
        jmp task_finish_ok

task_exec:
        lda TREQ_DESCRIPTOR
        bne task_invalid
        ldx TREQ_COUNT
        beq task_invalid
        cpx #$37
        bcs task_invalid
        lda #$00
        sta _udeks_shell_command_line,x
        dex
task_copy_command:
        lda TASK_COMMAND,x
        sta _udeks_shell_command_line,x
        dex
        bpl task_copy_command
        ; Never execute a resident command while the persistent bank-1 task
        ; gate is on the 8502 call stack. In particular, a nested Z80 handoff
        ; cannot safely resume through that bank-switched path. The ordinary
        ; bank-0 shell poll consumes the copied command on this same service
        ; pass. Report foreground/wait so ush does not emit a premature prompt.
        jmp task_exec_pending

task_wait:
        lda _udeks_shell_foreground_job
        beq task_finish_ok
        lda #$01
        bne task_finish_ok

task_prompt:
        jsr _udeks_root_terminal_prompt
        beq task_finish_ok
        lda #ERR_EIO
        bne task_finish_error

task_input_denied:
        jmp task_finish_error
task_would_block:
        lda #ERR_EAGAIN
        bne task_finish_error
task_invalid:
        lda #ERR_EINVAL
        bne task_finish_error
task_protocol_error:
        lda #ERR_EPROTO
task_finish_error:
        sta TREQ_ERROR
        lda #$00
        sta TREQ_RESULT
        lda #TREQ_STATE_ERROR
        sta TREQ_STATE
        clc
        rts

task_finish_ok:
        sta TREQ_RESULT
        lda #$00
        sta TREQ_ERROR
        lda #TREQ_COMPLETE
        sta TREQ_STATE
        lda #$00
        clc
        rts

task_signature:
        .byte 'U', 'T', 'R', 'Q', $00
        .assert * <= $f910, error, "task request gateway exceeds common reservation"
