; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .export _udeks_vdc_text_assets
        .export _udeks_vdc_text_assets_end

        .segment "VDCASSETS"
_udeks_vdc_text_assets:
        .incbin "build/assets/udeks-vdc-text.bin"
_udeks_vdc_text_assets_end:
        ; Only the 63*16 uploaded glyph bytes retire. Header/tile maps stay
        ; resident, and the paths overlay must never touch either neighbour.
        .assert _udeks_vdc_text_assets = $96a8, error, "VDC assets moved"
        .assert _udeks_vdc_text_assets_end = $9b00, error, "VDC assets changed size"
