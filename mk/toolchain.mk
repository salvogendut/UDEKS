# SPDX-License-Identifier: GPL-3.0-or-later

CC65 ?= cc65
CA65 ?= ca65
LD65 ?= ld65
CL65 ?= cl65

SDCC ?= sdcc
SDASZ80 ?= sdasz80
RASM ?= rasm
PYTHON ?= python3

# The kernel is a custom freestanding target, not a C128 KERNAL application.
CFLAGS_8502 := -t none --cpu 6502 --standard c99 -Oirs -I include
ASFLAGS_8502 := --cpu 6502 -I src/8502
LDFLAGS_8502 := -C cfg/8502-bootstrap.cfg -m build/8502/udeks-8502.map

CFLAGS_Z80 := -mz80 --std-c11 --opt-code-size -I include
LDFLAGS_Z80 := -mz80 --no-std-crt0 --code-loc 0x2000 --data-loc 0x3000

REQUIRED_TOOLS := $(CC65) $(CA65) $(LD65) $(CL65) $(SDCC) $(SDASZ80) $(RASM) $(PYTHON)
