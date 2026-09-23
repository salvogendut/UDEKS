; SPDX-License-Identifier: GPL-3.0-or-later
; Standalone RASM smoke image. It is not linked with SDCC objects.

                org   #2000

start
                di
spin
                jp    spin
image_end

                save  "build/z80/rasm-smoke.bin",start,image_end-start
