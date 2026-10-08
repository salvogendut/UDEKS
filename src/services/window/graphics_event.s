; SPDX-License-Identifier: GPL-3.0-or-later
; Private serialized graphics-service adapter, after caller/handle validation.
; Replaces the old EVENT marshalling without adding resident state. INPUT opts
; into held samples; legacy EVENT still returns only queued button-down edges.
        .setcpu "6502"
        .macpack longbranch
        .export _udeks_graphics_event
        .import _udeks_graphics_record
        .export _udeks_graphics_geometry, _udeks_retained_read
        .import _udeks_window_get_geometry, pusha, pushax
        .import _udeks_graphics_width, _udeks_graphics_height
        .import _udeks_graphics_origin_x, _udeks_graphics_origin_y
        .import _udeks_window_take_click, _udeks_window_is_dragging
        .import _udeks_window_is_focused, _udeks_window_update_busy
        .importzp ptr1
R = _udeks_graphics_record
P = R+14
        ; Small, shared marshalling helpers fund INPUT in the existing areas.
        ; These have the exact previous C signatures and no persistent state.
        .ifndef UDEKS_INPUT_TEST
        .segment "GRAPHICSHELP"
        .else
        .segment "CODE"
        .endif
_udeks_retained_read:
        sta ptr1
        stx ptr1+1
        ldy #7
read_byte:
        lda (ptr1),y
        sta P+2,y
        dey
        bpl read_byte
        rts
        .segment "CODE"
_udeks_graphics_geometry:
        jsr pusha
        lda #<_udeks_graphics_origin_x
        ldx #>_udeks_graphics_origin_x
        jsr pushax
        lda #<_udeks_graphics_origin_y
        ldx #>_udeks_graphics_origin_y
        jsr pushax
        lda #<_udeks_graphics_width
        ldx #>_udeks_graphics_width
        jsr pushax
        lda #<_udeks_graphics_height
        ldx #>_udeks_graphics_height
        jmp _udeks_window_get_geometry
        .ifndef UDEKS_INPUT_TEST
PTR = $f1d0
        .else
        .import _input_pointer
PTR = _input_pointer
        .endif
        .ifndef UDEKS_INPUT_TEST
        .segment "GRAPHICSCODE"
        .else
        .segment "CODE"
        .endif
_udeks_graphics_event:
        lda P+1
        sta P+8                 ; handle survives response writes
        lda #4
        sta R+11
        lda R+5
        cmp #10
        bcc click
        ldx #2
save_size:
        lda P+2,x
        sta P+9,x
        dex
        bpl save_size
        lda P+8
        jsr _udeks_graphics_geometry
        lda _udeks_graphics_width
        sta P+4
        lda _udeks_graphics_width+1
        sta P+5
        lda _udeks_graphics_height
        sta P+6
        lda P
        cmp #7
        lda #7
        adc #0
        sta R+11               ; INPUT adds signed Y high byte at P+7
        ldx #2
compare_size:
        lda P+4,x
        cmp P+9,x
        bne size_changed
        dex
        bpl compare_size
        bmi click
size_changed:
        lda P+8
        jsr _udeks_window_is_dragging
        cmp #0
        bne click
        lda #2
        jmp state
click:
        lda P+8
        jsr _udeks_window_take_click
        sta ptr1
        stx ptr1+1
        ora ptr1+1
        beq held
        ldy #2
copy_click:
        lda (ptr1),y
        sta P+1,y
        dey
        bpl copy_click
        lda #3
        jmp state
        .ifndef UDEKS_INPUT_TEST
        .segment "MODULECODE"
        .endif
state:
        sta P
        lda #0
        tax
        rts
        .ifndef UDEKS_INPUT_TEST
        .segment "GRAPHICSCODE"
        .endif
idle:
        lda #1
        jmp state
held:
        lda P
        cmp #7
        bne idle
        lda P+8
        jsr _udeks_window_is_focused
        cmp #0
        beq idle
        jsr _udeks_window_update_busy
        cmp #0
        bne idle
        ; Signed relative coordinates permit a captured client stroke to stop
        ; outside its canvas. Only INPUT returns Y high in byte 7. Clients own
        ; hit-testing; the compositor still clips all drawing independently.
        ; Atomic IRQ snapshot, with no function calls or global scratch.
        php
        sei
        lda PTR+11
        and #5                 ; mouse primary or joystick fire, not secondary
        bne :+
        plp
        jmp idle
:
        sec
        lda PTR+8
        sbc #12                ; sprite-hotspot to canvas coordinates
        sta P+1
        lda PTR+9
        sbc #0
        sta P+2
        sec
        lda P+1
        sbc _udeks_graphics_origin_x
        sta P+1
        lda P+2
        sbc _udeks_graphics_origin_x+1
        sta P+2
        sec
        lda PTR+10
        sbc #40
        sec
        sbc _udeks_graphics_origin_y
        sta P+3
        lda #0
        sbc #0
        sta P+7
        plp
        lda #4
        jmp state
