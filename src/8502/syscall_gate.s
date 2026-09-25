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
        .import _udeks_stream_write_byte
        .import _udeks_stream_write
        .import _udeks_line_editor_read
        .import _udeks_root_console_write
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
TREQ_PAYLOAD    = TREQ_BASE+$0e

TREQ_REQUEST    = $01
TREQ_COMPLETE   = $02
TREQ_STATE_ERROR = $80
TREQ_OP_READ    = $01
TREQ_OP_WRITE   = $02

ERR_EBADF       = $09
ERR_EAGAIN      = $0b
ERR_EINVAL      = $16
ERR_ENOSYS      = $26
ERR_EPROTO      = $47

_udeks_syscall_table:
        .byte 'U', 'S', 'Y', 'S'
        .byte $00, $02
        .byte $03, $10
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
        jmp task_request_dispatch
        .res 13, $ea

task_request_dispatch:
        jmp task_validate_request
task_protocol_trampoline:
        jmp task_protocol_error
task_validate_request:
        lda TREQ_BASE
        cmp #'U'
        bne task_protocol_trampoline
        lda TREQ_BASE+1
        cmp #'T'
        bne task_protocol_trampoline
        lda TREQ_BASE+2
        cmp #'R'
        bne task_protocol_trampoline
        lda TREQ_BASE+3
        cmp #'Q'
        bne task_protocol_trampoline
        lda TREQ_BASE+4
        bne task_protocol_trampoline
        lda TREQ_STATE
        cmp #TREQ_REQUEST
        bne task_protocol_trampoline
        lda TREQ_OPERATION
        cmp #TREQ_OP_READ
        beq task_read
        cmp #TREQ_OP_WRITE
        beq task_write
        lda #ERR_ENOSYS
        bne task_finish_error

task_read:
        lda TREQ_DESCRIPTOR
        bne task_bad_descriptor
        lda TREQ_COUNT
        cmp #$19
        bcs task_invalid
        lda #<TREQ_PAYLOAD
        ldx #>TREQ_PAYLOAD
        jsr pushax
        lda TREQ_COUNT
        jsr _udeks_line_editor_read
        cmp #$ff
        beq task_would_block
        sta TREQ_RESULT
        jmp task_finish_ok

task_write:
        lda TREQ_DESCRIPTOR
        cmp #$01
        beq task_write_valid
        cmp #$02
        bne task_bad_descriptor
task_write_valid:
        lda TREQ_COUNT
        cmp #$19
        bcs task_invalid
        ldx #$00
task_write_byte:
        cpx TREQ_COUNT
        bcs task_write_complete
        txa
        pha
        lda TREQ_PAYLOAD,x
        jsr _udeks_root_console_write
        pla
        tax
        inx
        bne task_write_byte
task_write_complete:
        lda TREQ_COUNT
        sta TREQ_RESULT

task_finish_ok:
        lda #$00
        sta TREQ_ERROR
        lda #TREQ_COMPLETE
        sta TREQ_STATE
        rts

task_protocol_error:
        lda #ERR_EPROTO
        bne task_finish_error
task_bad_descriptor:
        lda #ERR_EBADF
        bne task_finish_error
task_would_block:
        lda #ERR_EAGAIN
        bne task_finish_error
task_invalid:
        lda #ERR_EINVAL
task_finish_error:
        sta TREQ_ERROR
        lda #$00
        sta TREQ_RESULT
        lda #TREQ_STATE_ERROR
        sta TREQ_STATE
        lda TREQ_ERROR
        rts

        .assert _udeks_syscall_table = $cf00, error, "syscall table moved"
        .assert _udeks_syscall_write_byte_gate = $cf10, error, "write-byte gate moved"
        .assert _udeks_syscall_write_gate = $cf20, error, "write gate moved"
        .assert _udeks_syscall_task_request_gate = $cf30, error, "task request gate moved"
        .assert task_request_dispatch = $cf40, error, "task dispatcher moved"
        .assert * <= $d000, error, "syscalls overlap I/O aperture"
