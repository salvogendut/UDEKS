; SPDX-License-Identifier: GPL-3.0-or-later
; Within the existing $FFD0-$FFF9 handoff/interrupt reservation:
; Z80 return $FFD0-$FFE1, NMI $FFE2-$FFE9, Z80 bootstrap $FFED-$FFF4.
UDEKS_NMI_ENTRY = $ffe2
UDEKS_NMI_PENDING = $fff5
UDEKS_NMI_DRAINS = $fff6          ; 16-bit coalesced acknowledgements, wraps

.macro UDEKS_NMI_STUB
        pha
        lda #$01
        sta UDEKS_NMI_PENDING
        pla
        rti
.endmacro
