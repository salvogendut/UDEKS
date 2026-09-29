; SPDX-License-Identifier: GPL-3.0-or-later
;
; Qualification-only persistent task. It submits EXIT(37) through the real
; bank-task gate. Reaching the instruction after JSR is a kernel failure.

        .setcpu "6502"
        .segment "STARTUP"

TREQ_BASE               = $f359
TREQ_STATE              = TREQ_BASE+$06
TREQ_OPERATION          = TREQ_BASE+$07
TREQ_SEQUENCE           = TREQ_BASE+$08
TREQ_DESCRIPTOR         = TREQ_BASE+$09
TREQ_COUNT              = TREQ_BASE+$0a
TREQ_RESULT             = TREQ_BASE+$0b
TREQ_ERROR              = TREQ_BASE+$0c
TREQ_FLAGS              = TREQ_BASE+$0d
TREQ_PAYLOAD             = TREQ_BASE+$0e
TASK_REQUEST_GATE       = $ff16

_task_exit_probe_entry:
        lda #'U'
        sta TREQ_BASE+0
        lda #'T'
        sta TREQ_BASE+1
        lda #'R'
        sta TREQ_BASE+2
        lda #'Q'
        sta TREQ_BASE+3
        lda #$00
        sta TREQ_BASE+4                ; ABI major
        lda #$03
        sta TREQ_BASE+5                ; ABI minor
        lda #$0b
        sta TREQ_OPERATION
        lda #$01
        sta TREQ_SEQUENCE
        sta TREQ_COUNT
        lda #$25                       ; exit status 37
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_DESCRIPTOR
        sta TREQ_RESULT
        sta TREQ_ERROR
        sta TREQ_FLAGS
        lda #$01
        sta TREQ_STATE
        jsr TASK_REQUEST_GATE

        ; Successful EXIT is non-returning. Publish an unmistakable marker if
        ; the dead task is ever resumed.
        lda #$ee
        sta TREQ_RESULT
exit_returned:
        jmp exit_returned

        .assert _task_exit_probe_entry = $9000, error, "EXIT probe entry moved"
