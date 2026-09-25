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
        .import _udeks_root_console_write
        .import _udeks_root_terminal_prompt
        .import _udeks_shell_command_line
        .import _udeks_shell_foreground_job
        .import _udeks_bootfs_request
        .export _udeks_time_sync_ti
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
        .res 13, $ea

        ; $CF40: A=hour, X=minute, Y=second. Set the shared service clock and
        ; CIA1 TOD; the time service mirrors it into BASIC's TI counter.
_udeks_syscall_clock_set_gate:
        jmp clock_set_runtime
        .res 13, $ea

        .assert _udeks_syscall_table = $cf00, error, "syscall table moved"
        .assert _udeks_syscall_write_byte_gate = $cf10, error, "write-byte gate moved"
        .assert _udeks_syscall_write_gate = $cf20, error, "write gate moved"
        .assert _udeks_syscall_task_request_gate = $cf30, error, "task request gate moved"
        .assert _udeks_syscall_clock_set_gate = $cf40, error, "clock-set gate moved"
        .assert * = $cf50, error, "base syscall vectors exceed reserved slots"

        .include "app_gateway.s"

        .segment "CODE"
clock_set_runtime:
        cmp #$18
        bcs clock_set_invalid
        cpx #$3c
        bcs clock_set_invalid
        cpy #$3c
        bcs clock_set_invalid
        sta $f208
        stx $f209
        sty $f20a
        lda $dc0f
        and #$7f
        sta $dc0f
        lda $f208
        beq clock_set_midnight
        cmp #$0c
        beq clock_set_noon
        bcc clock_set_am
        sec
        sbc #$0c
        jsr clock_binary_bcd
        ora #$80
        bne clock_set_hour_ready
clock_set_midnight:
        ; The 6526 toggles PM when $12 is written. $00/$80 are the documented
        ; safe encodings for setting midnight/noon without that anomaly.
        lda #$00
        jmp clock_set_hour_ready
clock_set_noon:
        lda #$80
        bne clock_set_hour_ready
clock_set_am:
        jsr clock_binary_bcd
clock_set_hour_ready:
        sta $dc0b
        lda $f209
        jsr clock_binary_bcd
        sta $dc0a
        lda $f20a
        jsr clock_binary_bcd
        sta $dc09
        lda #$00
        sta $f20b
        sta $dc08
        inc $f20c
        jsr _udeks_time_sync_ti
        lda #$00
        rts
clock_set_invalid:
        lda #$01
        rts

clock_binary_bcd:
        ldx #$00
clock_binary_bcd_digit:
        cmp #$0a
        bcc clock_binary_bcd_ready
        sbc #$0a
        inx
        bne clock_binary_bcd_digit
clock_binary_bcd_ready:
        sta tmp1
        txa
        asl a
        asl a
        asl a
        asl a
        ora tmp1
        rts

        ; Rebuild BASIC's high/middle/low TI bytes from the published
        ; HH:MM:SS.t value. CIA TOD has tenth-second resolution, hence +6.
_udeks_time_sync_ti:
        lda $f20b
        cmp $f20c
        beq clock_sync_done
        sta $f20c
        lda #$00
        sta $a0
        sta $a1
        sta $a2
        ldy $f208
        ldx #$4b
        jsr clock_add_loop
        ldy $f209
        ldx #$0e
        jsr clock_add_loop
        ldy $f20a
        ldx #$00
        jsr clock_add_loop
        ldy $f20b
clock_add_tenth:
        beq clock_sync_done
        clc
        lda $a2
        adc #$06
        sta $a2
        bcc :+
        inc $a1
        bne :+
        inc $a0
:
        dey
        bne clock_add_tenth
clock_sync_done:
        rts

        ; Add Y copies of the constant selected by X. The high byte is $03
        ; only for hours; minutes and seconds cannot carry beyond their range.
clock_add_loop:
        sty tmp1
        tya
        beq clock_add_done
clock_add_again:
        cpx #$4b
        bne :+
        lda #$c0
        bne clock_add_value
:
        cpx #$0e
        bne :+
        lda #$10
        bne clock_add_value
:
        lda #$3c
clock_add_value:
        clc
        adc $a2
        sta $a2
        txa
        adc $a1
        sta $a1
        lda #$00
        adc $a0
        sta $a0
        ; Hour contributions need the additional fixed high-byte value.
        cpx #$4b
        bne :+
        clc
        lda $a0
        adc #$03
        sta $a0
:
        dec tmp1
        beq clock_add_done
        bne clock_add_again
clock_add_done:
        rts

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
        cmp #$03
        bcs task_protocol_trampoline
        lda TREQ_FLAGS
        bne task_protocol_trampoline
        lda TREQ_STATE
        cmp #TREQ_REQUEST
        bne task_protocol_trampoline
        jmp task_dispatch_operation
task_protocol_trampoline:
        jmp task_protocol_error
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
        bne :+
        jmp task_prompt
:
        jmp _udeks_bootfs_request

task_read:
        lda TREQ_DESCRIPTOR
        beq task_read_descriptor_ok
        jmp task_bad_descriptor
task_read_descriptor_ok:
        lda TREQ_COUNT
        cmp #$19
        bcc task_read_count_ok
        jmp task_invalid
task_read_count_ok:
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
        lda #$01
        sta SHELL_PENDING_EXEC
        bne task_finish_ok

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

task_bad_descriptor:
        lda #ERR_EBADF
        bne task_finish_error
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
        lda TREQ_ERROR
        rts

task_finish_ok:
        sta TREQ_RESULT
        lda #$00
        sta TREQ_ERROR
        lda #TREQ_COMPLETE
        sta TREQ_STATE
        lda #$00
        rts

task_signature:
        .byte 'U', 'T', 'R', 'Q', $00
        .assert * <= $f910, error, "task request gateway exceeds common reservation"
