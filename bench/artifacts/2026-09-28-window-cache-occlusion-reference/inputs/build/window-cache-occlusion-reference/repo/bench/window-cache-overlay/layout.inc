; SPDX-License-Identifier: GPL-3.0-or-later
; Private placement experiment, NOT a published UAPP or production allocation.
RUN = $f68a
CORE = $4200
CACHE = $4400
CACHE_LIMIT = $5c00
SHADOW = $a1e0
DIRTY = $e190
PARAM = $f780
OFFSET = PARAM                 ; logical shadow offset, little endian
ADDRESS = PARAM+2              ; packed bank-1 row address
STRIDE = PARAM+4               ; packed bytes (1..40)
RAWCOUNT = PARAM+5             ; shadow bytes (1..40)
SHIFT = PARAM+6                ; pixel bit offset (0..7)
LASTMASK = PARAM+7             ; valid high bits in packed last byte
MODE = PARAM+8                 ; 0 capture, 1 paste
STAGE = $f7b0                  ; 40 bytes, gateway-owned, never $F400
READ = RUN+3
WRITE = RUN+6
KERNEL = $ff01
WORKER = $ff04
