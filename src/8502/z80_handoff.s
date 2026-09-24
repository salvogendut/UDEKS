; SPDX-License-Identifier: GPL-3.0-or-later
;
; The first lease resumes the C128 Z80 reset BIOS at $FFED.  The installed
; eight-byte continuation selects the worker-I/O profile in bank 1 and jumps
; to the resident image at $2000.  Later leases resume after the Z80 OUT that
; returned ownership, so the continuation is used exactly once.

        .setcpu "6502"
        .export _udeks_z80_prepare
        .export _udeks_z80_handoff

MMU_MODE                = $d505
Z80_HANDOFF_GATEWAY     = $ffd0
Z80_CONTINUATION        = $ffed

        .segment "CODE"
_udeks_z80_prepare:
        ldx #z80_gateway_end-z80_gateway-1
copy_gateway:
        lda z80_gateway,x
        sta Z80_HANDOFF_GATEWAY,x
        dex
        bpl copy_gateway
        ldx #z80_bootstrap_end-z80_bootstrap-1
copy_bootstrap:
        lda z80_bootstrap,x
        sta Z80_CONTINUATION,x
        dex
        bpl copy_bootstrap
        rts

_udeks_z80_handoff:
        lda #$b0
        sta MMU_MODE
        rts

z80_gateway:
        .byte $3e, $3e             ; LD A,$3E: bank 0, I/O visible
        .byte $32, $00, $ff        ; LD ($FF00),A: restore kernel profile
        .byte $01, $05, $d5        ; LD BC,$D505
        .byte $3e, $b1             ; LD A,$B1: give ownership to 8502
        .byte $ed, $79             ; OUT (C),A
        .byte $3e, $7e             ; resume: LD A,$7E
        .byte $32, $00, $ff        ; restore worker profile before RET
        .byte $c9                  ; RET to the bank-1 caller
z80_gateway_end:
        .assert z80_gateway_end-z80_gateway = 18, error, "Z80 gateway size drift"
        .assert Z80_HANDOFF_GATEWAY+(z80_gateway_end-z80_gateway) <= Z80_CONTINUATION, error, "Z80 common gateways overlap"

z80_bootstrap:
        .byte $3e, $7e             ; LD A,$7E: bank 1, I/O visible
        .byte $32, $00, $ff        ; LD ($FF00),A: select worker profile
        .byte $c3, $00, $20        ; JP $2000
z80_bootstrap_end:
        .assert z80_bootstrap_end-z80_bootstrap = 8, error, "Z80 bootstrap size drift"
