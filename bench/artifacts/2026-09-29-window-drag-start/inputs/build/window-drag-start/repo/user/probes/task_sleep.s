; SPDX-License-Identifier: GPL-3.0-or-later
; Qualification-only persistent task for invalid and blocking SLEEP requests.

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

_task_sleep_probe_entry:
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
        lda #'S'
        sta PROBE+1
        lda #'L'
        sta PROBE+2
        lda #'0'
        sta PROBE+3

        lda #$00                       ; reject SLEEP(0)
        ldx #$71
        jsr sleep_request
        lda STATE
        sta PROBE+5
        lda ERROR
        sta PROBE+6
        lda SEQUENCE
        sta PROBE+7

        lda #<$0259                    ; reject SLEEP(601)
        ldx #$72
        ldy #>$0259
        jsr sleep_request_16
        lda STATE
        sta PROBE+8
        lda ERROR
        sta PROBE+9
        lda SEQUENCE
        sta PROBE+10

        lda #$01
        sta PROBE+4                    ; monitor may observe blocked state
wait_monitor:
        lda PROBE+15
        cmp #$5a
        bne wait_monitor
        lda #<$0258                    ; SLEEP(600), maximum ABI duration
        ldx #$73
        ldy #>$0258
        jsr sleep_request_16
        lda STATE
        sta PROBE+11
        lda RESULT
        sta PROBE+12
        lda ERROR
        sta PROBE+13
        lda SEQUENCE
        sta PROBE+14
        lda #$a5
        sta PROBE+4
done:
        jmp done

sleep_request:
        ldy #$00
sleep_request_16:
        sta PAYLOAD
        sty PAYLOAD+1
        stx SEQUENCE
        lda #$0d
        sta OPERATION
        lda #$02
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

        .assert _task_sleep_probe_entry = $9000, error, "SLEEP probe moved"
