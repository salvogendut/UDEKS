; SPDX-License-Identifier: GPL-3.0-or-later
;
; Qualification-only persistent parent task for production WAITPID. VICE
; seeds task 2 while this task waits on the common phase byte, first live and
; then zombie. Results are copied out of the shared request record before the
; next request overwrites it.

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

PROBE                    = $f280
PROBE_PHASE              = PROBE+$04

_task_waitpid_probe_entry:
        lda #'U'
        sta PROBE+0
        lda #'W'
        sta PROBE+1
        lda #'P'
        sta PROBE+2
        lda #'0'
        sta PROBE+3

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
        lda #$0c
        sta TREQ_OPERATION
        lda #$00
        sta TREQ_DESCRIPTOR
        lda #$02
        sta TREQ_COUNT

        lda #$01
        sta PROBE_PHASE
wait_live_seed:
        lda PROBE_PHASE
        cmp #$02
        bne wait_live_seed

        lda #$02                       ; specific child 2
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_PAYLOAD+1
        lda #$01                       ; NOHANG
        sta TREQ_FLAGS
        lda #$01
        sta TREQ_SEQUENCE
        jsr submit_waitpid
        lda TREQ_STATE
        sta PROBE+5
        lda TREQ_RESULT
        sta PROBE+6
        lda TREQ_ERROR
        sta PROBE+7
        lda TREQ_PAYLOAD
        sta PROBE+8
        lda TREQ_PAYLOAD+1
        sta PROBE+9

        lda #$03
        sta PROBE_PHASE
wait_zombie_seed:
        lda PROBE_PHASE
        cmp #$04
        bne wait_zombie_seed

        lda #$00                       ; any child; zombie wins
        sta TREQ_PAYLOAD
        sta TREQ_PAYLOAD+1
        sta TREQ_FLAGS
        lda #$02
        sta TREQ_SEQUENCE
        jsr submit_waitpid
        lda TREQ_STATE
        sta PROBE+10
        lda TREQ_RESULT
        sta PROBE+11
        lda TREQ_ERROR
        sta PROBE+12
        lda TREQ_PAYLOAD
        sta PROBE+13
        lda TREQ_PAYLOAD+1
        sta PROBE+14
        lda TREQ_PAYLOAD+2
        sta PROBE+15
        lda TREQ_PAYLOAD+3
        sta PROBE+16

        lda #$02                       ; reaped child is now absent
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_PAYLOAD+1
        lda #$01
        sta TREQ_FLAGS
        lda #$03
        sta TREQ_SEQUENCE
        jsr submit_waitpid
        lda TREQ_STATE
        sta PROBE+17
        lda TREQ_RESULT
        sta PROBE+18
        lda TREQ_ERROR
        sta PROBE+19

        ; A real second task is installed by the monitor after this parent
        ; enters WAITING.  The response must retain this sequence and may be
        ; published only when the parent is selected again.
        lda #$05
        sta PROBE_PHASE
wait_blocking_child:
        lda PROBE_PHASE
        cmp #$06
        bne wait_blocking_child
        lda #$02
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_PAYLOAD+1
        sta TREQ_FLAGS
        lda #$44
        sta TREQ_SEQUENCE
        jsr submit_waitpid
        lda TREQ_STATE
        sta PROBE+20
        lda TREQ_RESULT
        sta PROBE+21
        lda TREQ_ERROR
        sta PROBE+22
        lda TREQ_SEQUENCE
        sta PROBE+23
        lda TREQ_PAYLOAD
        sta PROBE+24
        lda TREQ_PAYLOAD+1
        sta PROBE+25
        lda TREQ_PAYLOAD+2
        sta PROBE+26
        lda TREQ_PAYLOAD+3
        sta PROBE+27

        lda #$a5
        sta PROBE_PHASE
probe_complete:
        jmp probe_complete

submit_waitpid:
        lda #$00
        sta TREQ_RESULT
        sta TREQ_ERROR
        lda #$01
        sta TREQ_STATE
        jsr TASK_REQUEST_GATE
        rts

        .assert *-_task_waitpid_probe_entry <= $0200, error, "WAITPID parent probe exceeds two pages"
        .res $0200-(*-_task_waitpid_probe_entry), $ea
task_waitpid_child_entry:
        .assert task_waitpid_child_entry = $9200, error, "WAITPID child entry moved"
        lda #$0b                       ; EXIT
        sta TREQ_OPERATION
        lda #$00
        sta TREQ_DESCRIPTOR
        sta TREQ_FLAGS
        lda #$01
        sta TREQ_COUNT
        lda #$ee
        sta TREQ_SEQUENCE
        lda #$25                       ; status 37
        sta TREQ_PAYLOAD
        lda #$01
        sta TREQ_STATE
        jsr TASK_REQUEST_GATE
        lda #$ff                       ; successful EXIT must never return
        sta PROBE_PHASE
child_returned:
        jmp child_returned

        .assert _task_waitpid_probe_entry = $9000, error, "WAITPID probe entry moved"
