; SPDX-License-Identifier: GPL-3.0-or-later
; Private experiment, not a published application or production allocation.
RUN = $f68a
KERNEL = $ff01
WORKER = $ff04
DISPATCH = $42d5
LEASE = $4cd0                 ; real cc65 sizeof = 13
GEOMETRY = LEASE+13           ; real cc65 sizeof = 6
ROW = GEOMETRY+6              ; real cc65 sizeof = 9
STACK_BOTTOM = $4d00
STACK_TOP = $4df0
CACHE = $4e00
CACHE_LIMIT = $5c00
OP = $f790                    ; six compiler-local operations
ARGS = $f793                  ; up to seven software-stack argument bytes
LAST_A = $f79a
LAST_X = $f79b
RESULT = $f79c
RETURN_SP = $f79d
INPUT_GEOMETRY = $f7a1
OUTPUT_ROW = $f7a7
OUTPUT_LEASE = $f7b0
ZP_FIRST = $06
ZP_BYTES = $1a
