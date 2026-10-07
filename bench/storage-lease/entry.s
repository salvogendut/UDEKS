; SPDX-License-Identifier: GPL-3.0-or-later
; This standalone probe owns both banks. Installs the EXACT linked service;
; its loader/scratch addresses are NOT a proposed production boot contract.
        .setcpu "6502"
        .export __STARTUP__ : absolute = 1
        .export _lease_request, _lease_cleanup, _lease_init
        .export _lease_arm, _lease_hidden, _lease_visible, _lease_stack
        .import _probe_main, zerobss
        .importzp sp
R = $f100
COPY = $f680
        .segment "STARTUP"
entry:
        sei
        cld
        ldx #$ff
        txs
        lda #$3e
        sta $ff00
        sta $d501
        lda #$7e
        sta $d503
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #0
        sta $d01a
        sta $dd0e
        sta $d508
        sta $d507
        sta $d50a
        lda #1
        sta $d509               ; CPU page zero/one pinned to bank 0
        lda $a0f0               ; harness VIC bank bit: 0 or $40
        and #$40
        ora #9
        sta $d506
        ldx #31
        lda #0
clear:  sta R,x
        dex
        bpl clear
        lda #1
        sta R+5
        lda $d506
        sta R+16
        ldx #common_end-common-1
copy_common:
        lda common,x
        sta COPY,x
        dex
        bpl copy_common
        jmp COPY
common:
        ldy #0
load:   lda entry,y
        sta $ff03
store:  sta entry,y
        sta $ff01
        iny
        bne load
        inc COPY+(load+2-common)
        inc COPY+(store+2-common)
        lda COPY+(load+2-common)
        cmp #>(image_end+$ff)
        bcc load
        sta $ff03
        jmp worker
finish:
        ldx #31
collect:
        lda R,x
        sta $ff01
        sta $a000,x
        dex
        bpl collect
halt:   jmp COPY+(halt-common)
common_end:
        .assert common_end-common <= $80, error, "probe common copier grew"

        .macro install source, target, length
        lda #<source
        sta $f8
        lda #>source
        sta $f9
        lda #<target
        sta $fa
        lda #>target
        sta $fb
        lda #<(length)
        sta $fc
        lda #>(length)
        sta $fd
        jsr copy
        .endmacro
worker:
        lda #0
        sta sp
        lda #$a0
        sta sp+1
        jsr zerobss
        install module, $1200, module_end-module
        install policy, $b000, policy_end-policy
        install driver, $e300, driver_end-driver
        lda $d506
        and #$f7
        sta $d506
        install hidden, $f000, hidden_end-hidden
        lda $d506
        ora #8
        sta $d506
        ldx #7
stub:   lda visible_stub,x
        sta $ffe2,x
        dex
        bpl stub
        lda #<observer
        sta $fffa
        lda #>observer
        sta $fffb
        lda #0
        sta $fff5
        jsr $120c
        sta R+7
        ; Instrument the vector, not the real hidden handler or lease exit.
        lda $d506
        and #$f7
        sta $d506
        lda #<observer
        sta $fffa
        lda #>observer
        sta $fffb
        lda $d506
        ora #8
        sta $d506
        ldx #$7f
        lda #$a5
guard:  sta $e180,x
        dex
        bpl guard
        jsr _probe_main
        jmp COPY+(finish-common)
copy:
        ldy #0
loop:   lda ($f8),y
        sta ($fa),y
        inc $f8
        bne :+
        inc $f9
:       inc $fa
        bne :+
        inc $fb
:       lda $fc
        bne :+
        dec $fd
:       dec $fc
        lda $fc
        ora $fd
        bne loop
        rts
visible_stub:
        pha
        lda #1
        sta $fff5
        pla
        rti
observer:
        pha
        lda $d506
        and #8
        beq :+
        inc _lease_visible
        bne observed
:       inc _lease_hidden
observed:
        pla
        jmp $ffe2

        .segment "CODE"
_lease_request:
        ldy #$00
        beq call
_lease_cleanup:
        ldy #$09
        bne call
_lease_init:
        ldy #$0c
call:
        sta caller
        stx caller+1
        sty invoke+1
        ldx #$1d
save_zp:
        lda $02,x
        pha
        dex
        bpl save_zp
        lda #$00
        sta sp
        lda #$e2
        sta sp+1
        lda _lease_arm
        beq disarmed
        lda $dd0d
        lda #0
        sta $dd04
        lda #$20
        sta $dd05
        lda #$81
        sta $dd0d
        lda #$19
        sta $dd0e
disarmed:
        lda caller
        ldx caller+1
invoke: jsr $1200
        sta result
        lda sp
        sta _lease_stack
        lda sp+1
        sta _lease_stack+1
        lda #$7f
        sta $dd0d
        lda $dd0d
        ldx #0
restore_zp:
        pla
        sta $02,x
        inx
        cpx #$1e
        bne restore_zp
        lda result
        ldx #0
        rts
        .segment "BSS"
caller: .res 2
result: .res 1
_lease_arm: .res 1
_lease_visible: .res 1
_lease_hidden: .res 1
_lease_stack: .res 2
        .segment "BLOBS"
module: .incbin "build/storage-write-lease/module.bin"
module_end:
policy: .incbin "build/storage-write-lease/policy.bin"
policy_end:
driver: .incbin "build/storage-write-lease/driver.bin"
driver_end:
hidden: .incbin "build/storage-write-lease/hidden.bin"
hidden_end:
image_end:
