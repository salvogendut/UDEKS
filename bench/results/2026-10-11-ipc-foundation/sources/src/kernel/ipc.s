; SPDX-License-Identifier: GPL-3.0-or-later
; Serialized, copied-message IPC. Two endpoints; one 16-byte mailbox each.
; Hidden bank-0 RAM is installed/checked at service startup. No C/ZP runtime.
        .setcpu "6502"
        .macpack longbranch
        .export _udeks_ipc_request, _udeks_ipc_retire
        .export _udeks_ipc_hidden_request, _udeks_ipc_hidden_retire
        .export _udeks_ipc_state, _udeks_ipc_serial
        .import _udeks_bootfs_finish_ok, _udeks_bootfs_finish_error
q = $f359
p = q+14
; Structure of arrays allows bounded absolute-indexed copies.
        .segment "BITMAPSTATE"
_udeks_ipc_state:
owner: .res 2
lo: .res 2
hi: .res 2
length: .res 2                  ; 0 empty; messages contain 1..16 bytes
senderlo: .res 2
senderhi: .res 2
names: .res 16                  ; zero padded, printable 1..8-byte name
data: .res 32
_udeks_ipc_serial: .res 2        ; monotonic, never wraps; ENOSPC at $ffff
caller: .res 1
target: .res 1
        .segment "CODE"
_udeks_ipc_request:
        sta $ff02
        jsr _udeks_ipc_hidden_request
        sta $ff01
        cmp #0
        bne ipc_error
        lda q+10
        jmp _udeks_bootfs_finish_ok
ipc_error:
        jmp _udeks_bootfs_finish_error
_udeks_ipc_retire:
        sta $ff02
        jsr _udeks_ipc_hidden_retire
        sta $ff01
        rts

        .segment "BITMAPCODE"
_udeks_ipc_hidden_request:
        sta caller
        cmp #1
        jcc denied
        cmp #9
        jcs denied
        lda q+5
        cmp #21
        jne invalid
        lda q+13
        jne invalid
        lda q+9
        cmp #2
        jcc named
        cmp #5
        jcs invalid
        lda q+10
        cmp #2
        jcc invalid
        ldy #0
        jsr handle
        jcs bad_handle
        stx target
        lda q+9
        cmp #2
        jeq send
        lda owner,x
        cmp caller
        jne denied
        lda q+9
        cmp #3
        jeq receive
        lda q+10
        cmp #2
        jne invalid
        jsr release
        jmp empty_reply
invalid: lda #22
        rts
bad_handle: lda #9
        rts
denied: lda #13
        rts
again: lda #11
        rts
size_error: lda #90
        rts
named:
        lda q+10
        beq invalid
        cmp #9
        bcs invalid
        ldy #0
validate_name:
        lda p,y
        cmp #33
        bcc invalid
        cmp #127
        bcs invalid
        iny
        cpy q+10
        bne validate_name
        ; Normalize padding in the common request, never caller memory.
        lda #0
:       cpy #8
        beq scan_names
        sta p,y
        iny
        bne :-
scan_names:
        ldx #1
next_name:
        lda owner,x
        beq no_match
        txa
        asl a
        asl a
        asl a
        tay
        stx target
        ldx #0
compare_name:
        lda names,y
        cmp p,x
        bne mismatch
        iny
        inx
        cpx #8
        bne compare_name
        ldx target
        lda q+9
        beq exists
        jmp handle_reply
mismatch:
        ldx target
no_match:
        dex
        bpl next_name
        lda q+9
        beq create
        lda #2
        rts
exists: lda #17
        rts
create:
        ldx #1
:       lda owner,x
        beq allocate
        dex
        bpl :-
full:   lda #28
        rts
allocate:
        lda _udeks_ipc_serial
        and _udeks_ipc_serial+1
        cmp #$ff
        beq full
        inc _udeks_ipc_serial
        bne :+
        inc _udeks_ipc_serial+1
:       lda _udeks_ipc_serial
        sta lo,x
        lda _udeks_ipc_serial+1
        sta hi,x
        lda caller
        sta owner,x
        lda #0
        sta length,x
        stx target
        txa
        asl a
        asl a
        asl a
        tay
        ldx #0
:       lda p,x
        sta names,y
        iny
        inx
        cpx #8
        bne :-
        ldx target
handle_reply:
        lda lo,x
        sta p
        lda hi,x
        sta p+1
        lda #2
        bne reply
empty_reply:
        lda #0
reply:  sta q+10
        lda #0
        rts

; Y points at a two-byte handle; returns X=endpoint, carry set if stale.
handle:
        ldx #1
:       lda owner,x
        beq :+
        lda lo,x
        cmp p,y
        bne :+
        lda hi,x
        cmp p+1,y
        beq found
:       dex
        bpl :--
        sec
        rts
found:  clc
        rts

send:
        lda q+10
        cmp #5
        jcc invalid
        cmp #21
        jcs invalid
        ldy #2
        jsr handle
        jcs bad_handle
        lda owner,x
        cmp caller
        jne denied
        ldx target
        lda length,x
        jne again
        lda p+2
        sta senderlo,x
        lda p+3
        sta senderhi,x
        lda q+10
        sec
        sbc #4
        sta length,x
        txa
        asl a
        asl a
        asl a
        asl a
        tay
        ldx #4
:       lda p,x
        sta data,y
        iny
        inx
        cpx q+10
        bne :-
        jmp empty_reply
receive:
        lda q+10
        cmp #3
        jne invalid
        lda p+2
        cmp #17
        jcs invalid
        lda length,x
        jeq again
        cmp p+2
        bcc :+
        beq :+
        jmp size_error
:       clc
        adc #2
        sta q+10
        lda senderlo,x
        sta p
        lda senderhi,x
        sta p+1
        lda #0
        sta length,x
        txa
        asl a
        asl a
        asl a
        asl a
        tay
        ldx #2
:       lda data,y
        sta p,x
        iny
        inx
        cpx q+10
        bne :-
        lda #0
        rts

; Invalidate this endpoint and messages sent from it before reuse.
release:
        lda #0
        sta owner,x
        sta length,x
        txa
        eor #1
        tay
        lda senderlo,y
        cmp lo,x
        bne released
        lda senderhi,y
        cmp hi,x
        bne released
        lda #0
        sta length,y
released:
        rts
_udeks_ipc_hidden_retire:
        sta caller
        ldx #1
:       lda owner,x
        cmp caller
        bne :+
        jsr release
:       dex
        bpl :--
        rts
