; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .export _udeks_vdc_text_assets
        .export _udeks_vdc_text_assets_end

        .segment "RODATA"
_udeks_vdc_text_assets:
        .incbin "build/assets/udeks-vdc-text.bin"
_udeks_vdc_text_assets_end:
