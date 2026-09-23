# SPDX-License-Identifier: GPL-3.0-or-later

SHELL := /bin/bash
.DEFAULT_GOAL := all

include mk/toolchain.mk

BUILD_DIR := build
BUILD_8502 := $(BUILD_DIR)/8502
BUILD_Z80 := $(BUILD_DIR)/z80

KERNEL_BIN := $(BUILD_8502)/udeks-8502.bin
Z80_IHX := $(BUILD_Z80)/udeks-z80.ihx
Z80_BIN := $(BUILD_Z80)/udeks-z80.bin
Z80_RASM_BIN := $(BUILD_Z80)/rasm-smoke.bin

.PHONY: all 8502 z80 z80-asm check doctor clean help

all: 8502 z80 z80-asm

8502: $(KERNEL_BIN)

z80: $(Z80_BIN)

z80-asm: $(Z80_RASM_BIN)

$(BUILD_8502) $(BUILD_Z80):
	mkdir -p $@

$(BUILD_8502)/kernel.s: src/8502/kernel.c include/udeks/mailbox.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/kernel.o: $(BUILD_8502)/kernel.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/crt0.o: src/8502/crt0.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(KERNEL_BIN): $(BUILD_8502)/crt0.o $(BUILD_8502)/kernel.o cfg/8502-bootstrap.cfg
	$(LD65) $(LDFLAGS_8502) -o $@ $(BUILD_8502)/crt0.o $(BUILD_8502)/kernel.o

$(BUILD_Z80)/worker.rel: src/z80/worker.c include/udeks/mailbox.h | $(BUILD_Z80)
	$(SDCC) $(CFLAGS_Z80) -c -o $@ $<

$(BUILD_Z80)/crt0.rel: src/z80/crt0.s | $(BUILD_Z80)
	$(SDASZ80) -o $@ $<

$(Z80_IHX): $(BUILD_Z80)/crt0.rel $(BUILD_Z80)/worker.rel
	$(SDCC) $(LDFLAGS_Z80) -o $@ $^

$(Z80_BIN): $(Z80_IHX) tools/ihx_to_bin.py
	$(PYTHON) tools/ihx_to_bin.py --start 0x2000 --end 0x4000 $< $@

$(Z80_RASM_BIN): src/z80/rasm_smoke.asm | $(BUILD_Z80)
	rm -f $@
	$(RASM) $< -eo >/dev/null
	test -s $@ || { echo "ERROR: RASM did not create $@" >&2; exit 1; }

check:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	$(PYTHON) -m py_compile tools/ihx_to_bin.py

doctor:
	@missing=0; \
	for tool in $(REQUIRED_TOOLS); do \
		if command -v "$$tool" >/dev/null 2>&1; then \
			printf '%-10s %s\n' "$$tool" "$$(command -v "$$tool")"; \
		else \
			printf '%-10s MISSING\n' "$$tool"; \
			missing=1; \
		fi; \
	done; \
	exit $$missing

clean:
	@test "$(abspath $(BUILD_DIR))" = "$(abspath build)" || { \
		echo "refusing to remove unexpected BUILD_DIR=$(BUILD_DIR)" >&2; exit 1; \
	}
	rm -rf -- $(BUILD_DIR)

help:
	@printf '%s\n' \
		'make            Build both CPU scaffolds and the RASM smoke image' \
		'make 8502       Build the freestanding 8502 scaffold' \
		'make z80        Build the SDCC Z80 worker scaffold' \
		'make z80-asm    Build the standalone RASM smoke image' \
		'make check      Run host-side tests' \
		'make doctor     Report missing build tools' \
		'make clean      Remove generated build artifacts'
