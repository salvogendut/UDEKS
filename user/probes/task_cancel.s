; SPDX-License-Identifier: GPL-3.0-or-later
; Qualification-only persistent parent for CANCEL and subsequent WAITPID.

        .setcpu "6502"
        .segment "STARTUP"

TREQ                    = $f359
STATE                   = TREQ+$06
OPERATION               = TREQ+$07
SEQUENCE                = TREQ+$08
DESCRIPTOR              = TREQ+$09
COUNT                   = TREQ+$0a
RESULT                  = TREQ+$0b
ERROR                   = TREQ+$0c
FLAGS                   = TREQ+$0d
PAYLOAD                 = TREQ+$0e
GATE                    = $ff16
PROBE                   = $f040
WAIT_SEED               = $91
WAIT_ZOMBIE             = $92

_task_cancel_probe_entry:
        lda #$00
        sta PROBE+4                    ; do not reuse the boot ABI minor as phase
        lda #'U'
        sta TREQ
        lda #'T'
        sta TREQ+1
        lda #'R'
        sta TREQ+2
        lda #'Q'
        sta TREQ+3
        lda #$00
        sta TREQ+4
        lda #$03
        sta TREQ+5

        lda #'U'
        sta PROBE
        lda #'C'
        sta PROBE+1
        lda #'N'
        sta PROBE+2
        lda #'0'
        sta PROBE+3

        lda #$00                       ; target 0 -> EINVAL
        ldx #$82
        ldy #$71
        jsr cancel_request
        lda STATE
        sta PROBE+5
        lda ERROR
        sta PROBE+6
        lda SEQUENCE
        sta PROBE+7

        lda #$01                       ; self -> EINVAL
        ldx #$82
        ldy #$72
        jsr cancel_request
        lda STATE
        sta PROBE+8
        lda ERROR
        sta PROBE+9
        lda SEQUENCE
        sta PROBE+10

        lda #$02                       ; free child -> ESRCH
        ldx #$82
        ldy #$73
        jsr cancel_request
        lda STATE
        sta PROBE+11
        lda ERROR
        sta PROBE+12
        lda SEQUENCE
        sta PROBE+13

        lda #WAIT_SEED
        sta PROBE+4
wait_seed:
        lda PROBE+4
        cmp #$a6
        bne wait_seed

        lda #$00                       ; $0100 is missing, not the zero selector
        ldx #$01
        ldy #$78
        jsr cancel_request_wide
        lda STATE
        sta PROBE+31
        lda ERROR
        sta PROBE+32
        lda SEQUENCE
        sta PROBE+33

        lda #$01                       ; $0101 is missing, not the current task
        ldx #$01
        ldy #$79
        jsr cancel_request_wide
        lda STATE
        sta PROBE+34
        lda ERROR
        sta PROBE+35
        lda SEQUENCE
        sta PROBE+36

        lda #$02                       ; $0102 must not cancel live child 2
        ldx #$01
        ldy #$7a
        jsr cancel_request_wide
        lda STATE
        sta PROBE+37
        lda ERROR
        sta PROBE+38
        lda SEQUENCE
        sta PROBE+39

        lda #$ff                       ; $ffff is missing, not a slot index
        ldx #$ff
        ldy #$7b
        jsr cancel_request_wide
        lda STATE
        sta PROBE+40
        lda ERROR
        sta PROBE+41
        lda SEQUENCE
        sta PROBE+42

        lda #$03                       ; unrelated live task -> ESRCH
        ldx #$82
        ldy #$74
        jsr cancel_request
        lda STATE
        sta PROBE+15
        lda ERROR
        sta PROBE+16
        lda SEQUENCE
        sta PROBE+17

        lda #$02                       ; blocked child -> ZOMBIE(130)
        ldx #$82
        ldy #$75
        jsr cancel_request
        lda STATE
        sta PROBE+18
        lda RESULT
        sta PROBE+19
        lda ERROR
        sta PROBE+20
        lda SEQUENCE
        sta PROBE+21

        lda #WAIT_ZOMBIE
        sta PROBE+4                    ; monitor checks zombie and wait cleanup
wait_zombie:
        lda PROBE+4
        cmp #$03
        bne wait_zombie

        lda #$02                       ; already-zombie -> ESRCH
        ldx #$82
        ldy #$76
        jsr cancel_request
        lda STATE
        sta PROBE+22
        lda ERROR
        sta PROBE+23
        lda SEQUENCE
        sta PROBE+24

        lda #$02                       ; reap status 130 with WAITPID NOHANG
        sta PAYLOAD
        lda #$00
        sta PAYLOAD+1
        lda #$77
        sta SEQUENCE
        lda #$0c
        sta OPERATION
        lda #$02
        sta COUNT
        lda #$01
        sta FLAGS
        lda #$00
        sta DESCRIPTOR
        sta RESULT
        sta ERROR
        lda #$01
        sta STATE
        jsr GATE
        lda STATE
        sta PROBE+25
        lda RESULT
        sta PROBE+26
        lda ERROR
        sta PROBE+27
        lda SEQUENCE
        sta PROBE+28
        lda PAYLOAD
        sta PROBE+29
        lda PAYLOAD+2
        sta PROBE+30

        lda #$a5
        sta PROBE+4
done:
        jmp done

; A=target low, X=status, Y=sequence. Target high is always zero here.
cancel_request:
        sta PAYLOAD
        lda #$00
        sta PAYLOAD+1
        stx PAYLOAD+2
        jmp cancel_submit

; A=target low, X=target high, Y=sequence. Status is always 130 here.
cancel_request_wide:
        sta PAYLOAD
        stx PAYLOAD+1
        lda #$82
        sta PAYLOAD+2
cancel_submit:
        sty SEQUENCE
        lda #$0e
        sta OPERATION
        lda #$03
        sta COUNT
        lda #$00
        sta DESCRIPTOR
        sta RESULT
        sta ERROR
        sta FLAGS
        lda #$01
        sta STATE
        jsr GATE
        rts

        .assert _task_cancel_probe_entry = $9000, error, "CANCEL probe moved"
