; SPDX-License-Identifier: GPL-3.0-or-later
;
; Qualification-only persistent parent for SPAWN. It creates the ordinary
; /bin/child UDEX, then blocks in WAITPID until the child's normal RTS is
; translated to EXIT(37) by the generated task-return trampoline.

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
TREQ_PAYLOAD            = TREQ_BASE+$0e
TASK_REQUEST_GATE       = $ff16

PROBE                   = $f040
PROBE_PHASE             = PROBE+$04

_task_spawn_parent_entry:
        lda #'U'
        sta TREQ_BASE+$00
        lda #'T'
        sta TREQ_BASE+$01
        lda #'R'
        sta TREQ_BASE+$02
        lda #'Q'
        sta TREQ_BASE+$03
        lda #$00
        sta TREQ_BASE+$04
        lda #$03
        sta TREQ_BASE+$05

        lda #$0f                       ; SPAWN
        sta TREQ_OPERATION
        lda #$33
        sta TREQ_SEQUENCE
        lda #$11
        sta TREQ_COUNT
        lda #$00
        sta TREQ_DESCRIPTOR
        sta TREQ_RESULT
        sta TREQ_ERROR
        sta TREQ_FLAGS
        ldx #$0f
clear_spawn_name:
        sta TREQ_PAYLOAD+$01,x
        dex
        bpl clear_spawn_name
        lda #$05
        sta TREQ_PAYLOAD+$00
        lda #'c'
        sta TREQ_PAYLOAD+$01
        lda #'h'
        sta TREQ_PAYLOAD+$02
        lda #'i'
        sta TREQ_PAYLOAD+$03
        lda #'l'
        sta TREQ_PAYLOAD+$04
        lda #'d'
        sta TREQ_PAYLOAD+$05
        lda #$01
        sta TREQ_STATE
        jsr TASK_REQUEST_GATE

        lda #'U'
        sta PROBE+$00
        lda #'S'
        sta PROBE+$01
        lda #'P'
        sta PROBE+$02
        lda #'0'
        sta PROBE+$03
        lda TREQ_STATE
        sta PROBE+$05
        lda TREQ_RESULT
        sta PROBE+$06
        lda TREQ_ERROR
        sta PROBE+$07
        lda TREQ_SEQUENCE
        sta PROBE+$08
        lda TREQ_PAYLOAD
        sta PROBE+$09
        lda TREQ_PAYLOAD+$01
        sta PROBE+$0a

        ; Only a successful task-2 admission may proceed to the blocking wait.
        lda TREQ_STATE
        cmp #$02
        beq :+
        jmp spawn_failed
:
        lda TREQ_RESULT
        cmp #$01
        beq :+
        jmp spawn_failed
:
        lda TREQ_PAYLOAD
        cmp #$02
        beq :+
        jmp spawn_failed
:
        lda TREQ_PAYLOAD+$01
        beq :+
        jmp spawn_failed
:

        lda #$0c                       ; WAITPID(2), blocking
        sta TREQ_OPERATION
        lda #$44
        sta TREQ_SEQUENCE
        lda #$02
        sta TREQ_COUNT
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_PAYLOAD+$01
        sta TREQ_DESCRIPTOR
        sta TREQ_RESULT
        sta TREQ_ERROR
        sta TREQ_FLAGS
        lda #$01
        sta TREQ_STATE
        jsr TASK_REQUEST_GATE

        lda TREQ_STATE
        sta PROBE+$0b
        lda TREQ_RESULT
        sta PROBE+$0c
        lda TREQ_ERROR
        sta PROBE+$0d
        lda TREQ_SEQUENCE
        sta PROBE+$0e
        lda TREQ_PAYLOAD
        sta PROBE+$0f
        lda TREQ_PAYLOAD+$01
        sta PROBE+$10
        lda TREQ_PAYLOAD+$02
        sta PROBE+$11
        lda TREQ_PAYLOAD+$03
        sta PROBE+$12

        ; Reuse the fully reaped slot and reinstall the common launcher.
        lda #$0f
        sta TREQ_OPERATION
        lda #$55
        sta TREQ_SEQUENCE
        lda #$11
        sta TREQ_COUNT
        lda #$00
        sta TREQ_DESCRIPTOR
        sta TREQ_RESULT
        sta TREQ_ERROR
        sta TREQ_FLAGS
        ldx #$0f
clear_second_spawn_name:
        sta TREQ_PAYLOAD+$01,x
        dex
        bpl clear_second_spawn_name
        lda #$05
        sta TREQ_PAYLOAD+$00
        lda #'c'
        sta TREQ_PAYLOAD+$01
        lda #'h'
        sta TREQ_PAYLOAD+$02
        lda #'i'
        sta TREQ_PAYLOAD+$03
        lda #'l'
        sta TREQ_PAYLOAD+$04
        lda #'d'
        sta TREQ_PAYLOAD+$05
        lda #$01
        sta TREQ_STATE
        jsr TASK_REQUEST_GATE
        lda TREQ_STATE
        sta PROBE+$13
        lda TREQ_RESULT
        sta PROBE+$14
        lda TREQ_ERROR
        sta PROBE+$15
        lda TREQ_SEQUENCE
        sta PROBE+$16
        lda TREQ_PAYLOAD
        sta PROBE+$17
        lda TREQ_PAYLOAD+$01
        sta PROBE+$18

        lda TREQ_STATE
        cmp #$02
        bne spawn_failed
        lda TREQ_RESULT
        cmp #$01
        bne spawn_failed
        lda TREQ_PAYLOAD
        cmp #$02
        bne spawn_failed
        lda TREQ_PAYLOAD+$01
        bne spawn_failed

        lda #$0c
        sta TREQ_OPERATION
        lda #$66
        sta TREQ_SEQUENCE
        lda #$02
        sta TREQ_COUNT
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_PAYLOAD+$01
        sta TREQ_DESCRIPTOR
        sta TREQ_RESULT
        sta TREQ_ERROR
        sta TREQ_FLAGS
        lda #$01
        sta TREQ_STATE
        jsr TASK_REQUEST_GATE
        lda TREQ_STATE
        sta PROBE+$19
        lda TREQ_RESULT
        sta PROBE+$1a
        lda TREQ_ERROR
        sta PROBE+$1b
        lda TREQ_SEQUENCE
        sta PROBE+$1c
        lda TREQ_PAYLOAD
        sta PROBE+$1d
        lda TREQ_PAYLOAD+$01
        sta PROBE+$1e
        lda TREQ_PAYLOAD+$02
        sta PROBE+$1f
        lda TREQ_PAYLOAD+$03
        sta PROBE+$20

        lda #$a5
        sta PROBE_PHASE
probe_complete:
        jmp probe_complete

spawn_failed:
        lda #$ee
        sta PROBE_PHASE
        jmp spawn_failed

        .assert _task_spawn_parent_entry = $9000, error, "SPAWN parent entry moved"
