; SPDX-License-Identifier: GPL-3.0-or-later
; Compact VDC running-application panel. Kept in the high-memory module so
; APP1 and APP2 remain entirely available to loadable graphical programs.

        .setcpu "6502"
        .export _udeks_console_app_panel_initialize
        .export _udeks_console_poll
        .import _udeks_vdc_write_block
        .import _udeks_vdc_block_source
        .import _udeks_vdc_block_address
        .import _udeks_vdc_block_length
        .import _udeks_vdc_text_assets

CONSOLE_STATUS  = $f070
VIC_STATUS      = $f1b0
XCLOCK_STATUS   = $f220
XWAVE_STATUS    = $f260
APP_MASK        = CONSOLE_STATUS+19
APP_UPDATES_LO  = CONSOLE_STATUS+20
APP_UPDATES_HI  = CONSOLE_STATUS+21

        .segment "BSS"
panel_buffer:   .res 11
panel_row:      .res 1
panel_mask:     .res 1
panel_slot:     .res 1

        .segment "MODULERODATA"
panel_screen_lo: .byte <$04b1, <$0501, <$0551, <$05a1, <$05f1, <$0641, <$0691
panel_screen_hi: .byte >$04b1, >$0501, >$0551, >$05a1, >$05f1, >$0641, >$0691
panel_attr_lo:   .byte <$0cb1, <$0d01, <$0d51, <$0da1, <$0df1, <$0e41, <$0e91
panel_attr_hi:   .byte >$0cb1, >$0d01, >$0d51, >$0da1, >$0df1, >$0e41, >$0e91
panel_title:     .byte 18,21,14,14,9,14,7,0
panel_none:      .byte 14,15,14,5,0
panel_xinit:     .byte 24,9,14,9,20,0
panel_xclock:    .byte 24,3,12,15,3,11,0
panel_xwave:     .byte 24,23,1,22,5,0

        .segment "MODULECODE"
_udeks_console_app_panel_initialize:
        lda #$ff
        sta APP_MASK
        jmp _udeks_console_poll

_udeks_console_poll:
        lda #$00
        ldx VIC_STATUS+5
        cpx #$03
        bne :+
        ora #$01
:
        ldx XCLOCK_STATUS+5
        cpx #$03
        bne :+
        ora #$02
:
        ldx XWAVE_STATUS+5
        cpx #$03
        bne :+
        ora #$04
:
        cmp APP_MASK
        bne panel_changed
        lda #$00
        rts
panel_changed:
        sta panel_mask
        jsr panel_draw_edges
        bne panel_error
        lda #<panel_title
        ldx #>panel_title
        ldy #$01
        jsr panel_draw_text
        bne panel_error

        lda #$00
        sta panel_slot
        lda panel_mask
        and #$01
        beq :+
        lda #<panel_xinit
        ldx #>panel_xinit
        jsr panel_draw_app
        bne panel_error
:
        lda panel_mask
        and #$02
        beq :+
        lda #<panel_xclock
        ldx #>panel_xclock
        jsr panel_draw_app
        bne panel_error
:
        lda panel_mask
        and #$04
        beq :+
        lda #<panel_xwave
        ldx #>panel_xwave
        jsr panel_draw_app
        bne panel_error
:
        lda panel_slot
        bne panel_clear_remaining
        lda #<panel_none
        ldx #>panel_none
        jsr panel_draw_app
        bne panel_error
panel_clear_remaining:
        lda panel_slot
        cmp #$03
        bcs panel_draw_spacer
        lda #$00
        tax
        jsr panel_draw_app
        beq panel_clear_remaining
panel_draw_spacer:
        lda #$00
        tax
        ldy #$05
        jsr panel_draw_text
        bne panel_error
        lda panel_mask
        sta APP_MASK
        inc APP_UPDATES_LO
        bne :+
        inc APP_UPDATES_HI
:
        lda #$00
        rts
panel_error:
        lda #$01
        rts

panel_draw_app:
        ldy panel_slot
        iny
        iny
        inc panel_slot
        ; Fall through with AX=text and Y=panel row.
panel_draw_text:
        sta panel_text_load+1
        stx panel_text_load+2
        sty panel_row
        lda _udeks_vdc_text_assets+15
        sta panel_buffer
        sta panel_buffer+10
        lda #$20
        ldx #$09
:
        sta panel_buffer,x
        dex
        bne :-
        lda panel_text_load+1
        ora panel_text_load+2
        beq panel_text_ready
        ldy #$00
:
panel_text_load:
        lda $ffff,y
        beq panel_text_ready
        sta panel_buffer+1,y
        iny
        cpy #$09
        bcc :-
panel_text_ready:
        ldx panel_row
        jsr panel_write_screen
        bne panel_text_done
        lda #$00
        ldx #$0a
:
        sta panel_buffer,x
        dex
        bpl :-
        lda panel_row
        cmp #$02
        bcc panel_attr_ready
        cmp #$05
        bcs panel_attr_ready
        lda #$80
        ldx #$09
:
        sta panel_buffer,x
        dex
        bne :-
panel_attr_ready:
        ldx panel_row
        jsr panel_write_attr
panel_text_done:
        rts

panel_draw_edges:
        lda _udeks_vdc_text_assets+10
        sta panel_buffer
        lda _udeks_vdc_text_assets+11
        sta panel_buffer+10
        lda _udeks_vdc_text_assets+14
        ldx #$09
:
        sta panel_buffer,x
        dex
        bne :-
        ldx #$00
        jsr panel_write_screen
        bne panel_edges_done
        lda _udeks_vdc_text_assets+12
        sta panel_buffer
        lda _udeks_vdc_text_assets+13
        sta panel_buffer+10
        ldx #$06
        jsr panel_write_screen
panel_edges_done:
        rts

panel_write_screen:
        lda panel_screen_lo,x
        sta _udeks_vdc_block_address
        lda panel_screen_hi,x
        sta _udeks_vdc_block_address+1
        jmp panel_write
panel_write_attr:
        lda panel_attr_lo,x
        sta _udeks_vdc_block_address
        lda panel_attr_hi,x
        sta _udeks_vdc_block_address+1
panel_write:
        lda #<panel_buffer
        sta _udeks_vdc_block_source
        lda #>panel_buffer
        sta _udeks_vdc_block_source+1
        lda #$0b
        sta _udeks_vdc_block_length
        lda #$00
        sta _udeks_vdc_block_length+1
        jmp _udeks_vdc_write_block
