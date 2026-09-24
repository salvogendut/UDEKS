# SPDX-License-Identifier: GPL-3.0-or-later

SHELL := /bin/bash
.DEFAULT_GOAL := all

include mk/toolchain.mk

BUILD_DIR := build
BUILD_8502 := $(BUILD_DIR)/8502
BUILD_Z80 := $(BUILD_DIR)/z80
BUILD_BENCH_8502 := $(BUILD_DIR)/bench/8502
BUILD_BENCH_Z80 := $(BUILD_DIR)/bench/z80
BUILD_IRQ_8502 := $(BUILD_DIR)/bench/irq/8502
BUILD_IRQ_Z80 := $(BUILD_DIR)/bench/irq/z80
BUILD_IRQ_SERVICE_8502 := $(BUILD_DIR)/bench/irq-service/8502
BUILD_IRQ_SERVICE_Z80 := $(BUILD_DIR)/bench/irq-service/z80
BUILD_CONTEXT_8502 := $(BUILD_DIR)/bench/context/8502
BUILD_CONTEXT_Z80 := $(BUILD_DIR)/bench/context/z80
BUILD_KERNEL_8502 := $(BUILD_DIR)/bench/kernel/8502
BUILD_KERNEL_Z80 := $(BUILD_DIR)/bench/kernel/z80
BUILD_HANDOFF_8502 := $(BUILD_DIR)/bench/handoff/8502
BUILD_HANDOFF_Z80 := $(BUILD_DIR)/bench/handoff/z80
BUILD_OFFLOAD_8502 := $(BUILD_DIR)/bench/offload/8502
BUILD_OFFLOAD_Z80 := $(BUILD_DIR)/bench/offload/z80
BUILD_MEMORY_MAP := $(BUILD_DIR)/bench/memory-map

KERNEL_BIN := $(BUILD_8502)/udeks-8502.bin
KERNEL_PRG := $(BUILD_8502)/udeks-8502.prg
Z80_IHX := $(BUILD_Z80)/udeks-z80.ihx
Z80_BIN := $(BUILD_Z80)/udeks-z80.bin
Z80_RASM_BIN := $(BUILD_Z80)/rasm-smoke.bin
BENCH_8502_BIN := $(BUILD_BENCH_8502)/bench-8502.bin
BENCH_8502_PRG := $(BUILD_BENCH_8502)/bench-8502.prg
BENCH_Z80_IHX := $(BUILD_BENCH_Z80)/bench-z80.ihx
BENCH_Z80_BIN := $(BUILD_BENCH_Z80)/bench-z80.bin
BENCH_Z80_LAUNCH_BIN := $(BUILD_BENCH_Z80)/bench-z80-launch.bin
BENCH_Z80_PRG := $(BUILD_BENCH_Z80)/bench-z80.prg
IRQ_8502_BIN := $(BUILD_IRQ_8502)/irq-8502.bin
IRQ_8502_PRG := $(BUILD_IRQ_8502)/irq-8502.prg
IRQ_Z80_IHX := $(BUILD_IRQ_Z80)/irq-z80.ihx
IRQ_Z80_BIN := $(BUILD_IRQ_Z80)/irq-z80.bin
IRQ_Z80_LAUNCH_BIN := $(BUILD_IRQ_Z80)/irq-z80-launch.bin
IRQ_Z80_PRG := $(BUILD_IRQ_Z80)/irq-z80.prg
IRQ_SERVICE_8502_BIN := $(BUILD_IRQ_SERVICE_8502)/irq-service-8502.bin
IRQ_SERVICE_8502_PRG := $(BUILD_IRQ_SERVICE_8502)/irq-service-8502.prg
IRQ_SERVICE_Z80_IHX := $(BUILD_IRQ_SERVICE_Z80)/irq-service-z80.ihx
IRQ_SERVICE_Z80_BIN := $(BUILD_IRQ_SERVICE_Z80)/irq-service-z80.bin
IRQ_SERVICE_Z80_LAUNCH_BIN := $(BUILD_IRQ_SERVICE_Z80)/irq-service-z80-launch.bin
IRQ_SERVICE_Z80_PRG := $(BUILD_IRQ_SERVICE_Z80)/irq-service-z80.prg
CONTEXT_8502_BIN := $(BUILD_CONTEXT_8502)/context-8502.bin
CONTEXT_8502_PRG := $(BUILD_CONTEXT_8502)/context-8502.prg
CONTEXT_Z80_IHX := $(BUILD_CONTEXT_Z80)/context-z80.ihx
CONTEXT_Z80_BIN := $(BUILD_CONTEXT_Z80)/context-z80.bin
CONTEXT_Z80_LAUNCH_BIN := $(BUILD_CONTEXT_Z80)/context-z80-launch.bin
CONTEXT_Z80_PRG := $(BUILD_CONTEXT_Z80)/context-z80.prg
KERNEL_8502_BIN := $(BUILD_KERNEL_8502)/kernel-8502.bin
KERNEL_8502_PRG := $(BUILD_KERNEL_8502)/kernel-8502.prg
KERNEL_Z80_IHX := $(BUILD_KERNEL_Z80)/kernel-z80.ihx
KERNEL_Z80_BIN := $(BUILD_KERNEL_Z80)/kernel-z80.bin
KERNEL_Z80_LAUNCH_BIN := $(BUILD_KERNEL_Z80)/kernel-z80-launch.bin
KERNEL_Z80_PRG := $(BUILD_KERNEL_Z80)/kernel-z80.prg
HANDOFF_8502_BIN := $(BUILD_HANDOFF_8502)/handoff-8502.bin
HANDOFF_Z80_IHX := $(BUILD_HANDOFF_Z80)/handoff-z80.ihx
HANDOFF_Z80_BIN := $(BUILD_HANDOFF_Z80)/handoff-z80.bin
HANDOFF_LAUNCH_BIN := $(BUILD_HANDOFF_8502)/handoff-launch.bin
HANDOFF_PRG := $(BUILD_HANDOFF_8502)/handoff.prg
OFFLOAD_8502_BIN := $(BUILD_OFFLOAD_8502)/offload-8502.bin
OFFLOAD_Z80_IHX := $(BUILD_OFFLOAD_Z80)/offload-z80.ihx
OFFLOAD_Z80_BIN := $(BUILD_OFFLOAD_Z80)/offload-z80.bin
OFFLOAD_LAUNCH_BIN := $(BUILD_OFFLOAD_8502)/offload-launch.bin
OFFLOAD_PRG := $(BUILD_OFFLOAD_8502)/offload.prg
MEMORY_MAP_GATEWAY_BIN := $(BUILD_MEMORY_MAP)/gateway.bin
MEMORY_MAP_LAUNCH_BIN := $(BUILD_MEMORY_MAP)/memory-map.bin
MEMORY_MAP_PRG := $(BUILD_MEMORY_MAP)/memory-map.prg

.PHONY: all 8502 z80 z80-asm bench bench-8502 bench-z80 bench-irq \
	bench-irq-8502 bench-irq-z80 bench-irq-service \
	bench-irq-service-8502 bench-irq-service-z80 bench-context \
	bench-context-8502 bench-context-z80 bench-kernel bench-kernel-8502 \
	bench-kernel-z80 bench-handoff bench-offload bench-memory-map \
	check doctor clean help

all: 8502 z80 z80-asm

8502: $(KERNEL_BIN) $(KERNEL_PRG)

z80: $(Z80_BIN)

z80-asm: $(Z80_RASM_BIN)

bench: bench-8502 bench-z80

bench-8502: $(BENCH_8502_BIN) $(BENCH_8502_PRG)

bench-z80: $(BENCH_Z80_BIN) $(BENCH_Z80_PRG)

bench-irq: bench-irq-8502 bench-irq-z80

bench-irq-8502: $(IRQ_8502_BIN) $(IRQ_8502_PRG)

bench-irq-z80: $(IRQ_Z80_BIN) $(IRQ_Z80_PRG)

bench-irq-service: bench-irq-service-8502 bench-irq-service-z80

bench-irq-service-8502: $(IRQ_SERVICE_8502_BIN) $(IRQ_SERVICE_8502_PRG)

bench-irq-service-z80: $(IRQ_SERVICE_Z80_BIN) $(IRQ_SERVICE_Z80_PRG)

bench-context: bench-context-8502 bench-context-z80

bench-context-8502: $(CONTEXT_8502_BIN) $(CONTEXT_8502_PRG)

bench-context-z80: $(CONTEXT_Z80_BIN) $(CONTEXT_Z80_PRG)

bench-kernel: bench-kernel-8502 bench-kernel-z80

bench-kernel-8502: $(KERNEL_8502_BIN) $(KERNEL_8502_PRG)

bench-kernel-z80: $(KERNEL_Z80_BIN) $(KERNEL_Z80_PRG)

bench-handoff: $(HANDOFF_PRG)

bench-offload: $(OFFLOAD_PRG)

bench-memory-map: $(MEMORY_MAP_PRG)

$(BUILD_8502) $(BUILD_Z80) $(BUILD_BENCH_8502) $(BUILD_BENCH_Z80) \
		$(BUILD_IRQ_8502) $(BUILD_IRQ_Z80) $(BUILD_IRQ_SERVICE_8502) \
		$(BUILD_IRQ_SERVICE_Z80) $(BUILD_CONTEXT_8502) $(BUILD_CONTEXT_Z80) \
		$(BUILD_KERNEL_8502) $(BUILD_KERNEL_Z80) $(BUILD_HANDOFF_8502) \
		$(BUILD_HANDOFF_Z80) $(BUILD_OFFLOAD_8502) $(BUILD_OFFLOAD_Z80) \
		$(BUILD_MEMORY_MAP):
	mkdir -p $@

$(BUILD_8502)/kernel.s: src/8502/kernel.c include/udeks/mailbox.h \
		include/udeks/memory.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/kernel.o: $(BUILD_8502)/kernel.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/crt0.o: src/8502/crt0.s src/8502/mmu.inc | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(KERNEL_BIN): $(BUILD_8502)/crt0.o $(BUILD_8502)/kernel.o cfg/8502-bootstrap.cfg
	$(LD65) $(LDFLAGS_8502) -o $@ $(BUILD_8502)/crt0.o $(BUILD_8502)/kernel.o

$(KERNEL_PRG): $(KERNEL_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2000 $< $@

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

$(BUILD_BENCH_8502)/main.s: bench/8502/main.c bench/include/udeks/bench.h | $(BUILD_BENCH_8502)
	$(CC65) $(CFLAGS_8502) -I bench/include -o $@ $<

$(BUILD_BENCH_8502)/runner.s: bench/common/runner.c bench/include/udeks/bench.h | $(BUILD_BENCH_8502)
	$(CC65) $(CFLAGS_8502) -I bench/include -o $@ $<

$(BUILD_BENCH_8502)/workloads.s: bench/common/workloads.c bench/include/udeks/bench.h | $(BUILD_BENCH_8502)
	$(CC65) $(CFLAGS_8502) -I bench/include -o $@ $<

$(BUILD_BENCH_8502)/%.o: $(BUILD_BENCH_8502)/%.s | $(BUILD_BENCH_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_BENCH_8502)/crt0.o: bench/8502/crt0.s | $(BUILD_BENCH_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_BENCH_8502)/timer.o: bench/8502/timer.s | $(BUILD_BENCH_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BENCH_8502_BIN): $(BUILD_BENCH_8502)/crt0.o \
		$(BUILD_BENCH_8502)/timer.o $(BUILD_BENCH_8502)/main.o \
		$(BUILD_BENCH_8502)/runner.o $(BUILD_BENCH_8502)/workloads.o \
		cfg/8502-bootstrap.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-bootstrap.cfg \
		-m $(BUILD_BENCH_8502)/bench-8502.map -o $@ \
		$(filter %.o,$^)

$(BENCH_8502_PRG): $(BENCH_8502_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2000 $< $@

$(BUILD_BENCH_Z80)/main.rel: bench/z80/main.c bench/include/udeks/bench.h | $(BUILD_BENCH_Z80)
	$(SDCC) $(CFLAGS_Z80) -I bench/include -c -o $@ $<

$(BUILD_BENCH_Z80)/runner.rel: bench/common/runner.c bench/include/udeks/bench.h | $(BUILD_BENCH_Z80)
	$(SDCC) $(CFLAGS_Z80) -I bench/include -c -o $@ $<

$(BUILD_BENCH_Z80)/workloads.rel: bench/common/workloads.c bench/include/udeks/bench.h | $(BUILD_BENCH_Z80)
	$(SDCC) $(CFLAGS_Z80) -I bench/include -c -o $@ $<

$(BUILD_BENCH_Z80)/crt0.rel: bench/z80/crt0.s | $(BUILD_BENCH_Z80)
	$(SDASZ80) -o $@ $<

$(BUILD_BENCH_Z80)/timer.rel: bench/z80/timer.s | $(BUILD_BENCH_Z80)
	$(SDASZ80) -o $@ $<

$(BENCH_Z80_IHX): $(BUILD_BENCH_Z80)/crt0.rel \
		$(BUILD_BENCH_Z80)/timer.rel $(BUILD_BENCH_Z80)/main.rel \
		$(BUILD_BENCH_Z80)/runner.rel $(BUILD_BENCH_Z80)/workloads.rel
	$(SDCC) $(LDFLAGS_Z80) -o $@ $^

$(BENCH_Z80_BIN): $(BENCH_Z80_IHX) tools/ihx_to_bin.py
	$(PYTHON) tools/ihx_to_bin.py --start 0x2000 --end 0x4000 $< $@

$(BUILD_BENCH_Z80)/launcher.o: bench/z80/launcher.s $(BENCH_Z80_BIN) | $(BUILD_BENCH_Z80)
	$(CA65) --cpu 6502 -o $@ $<

$(BENCH_Z80_LAUNCH_BIN): $(BUILD_BENCH_Z80)/launcher.o cfg/8502-z80-launcher.cfg
	$(LD65) -C cfg/8502-z80-launcher.cfg -o $@ $<

$(BENCH_Z80_PRG): $(BENCH_Z80_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x1fe0 $< $@

$(BUILD_IRQ_8502)/irq.o: bench/irq/8502.s | $(BUILD_IRQ_8502)
	$(CA65) --cpu 6502 -o $@ $<

$(IRQ_8502_BIN): $(BUILD_IRQ_8502)/irq.o cfg/8502-irq-probe.cfg
	$(LD65) -C cfg/8502-irq-probe.cfg -o $@ $<

$(IRQ_8502_PRG): $(IRQ_8502_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@

$(BUILD_IRQ_Z80)/irq.rel: bench/irq/z80.s | $(BUILD_IRQ_Z80)
	$(SDASZ80) -o $@ $<

$(IRQ_Z80_IHX): $(BUILD_IRQ_Z80)/irq.rel
	$(SDCC) -mz80 --no-std-crt0 --code-loc 0x2800 \
		-o $@ $^

$(IRQ_Z80_BIN): $(IRQ_Z80_IHX) tools/ihx_to_bin.py
	$(PYTHON) tools/ihx_to_bin.py --start 0x2800 --end 0x3000 $< $@

$(BUILD_IRQ_Z80)/launcher.o: bench/irq/z80-launcher.s $(IRQ_Z80_BIN) | $(BUILD_IRQ_Z80)
	$(CA65) --cpu 6502 -o $@ $<

$(IRQ_Z80_LAUNCH_BIN): $(BUILD_IRQ_Z80)/launcher.o cfg/8502-z80-irq-launcher.cfg
	$(LD65) -C cfg/8502-z80-irq-launcher.cfg -o $@ $<

$(IRQ_Z80_PRG): $(IRQ_Z80_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x27d0 $< $@

$(BUILD_IRQ_SERVICE_8502)/irq.o: bench/irq-service/8502.s | $(BUILD_IRQ_SERVICE_8502)
	$(CA65) --cpu 6502 -o $@ $<

$(IRQ_SERVICE_8502_BIN): $(BUILD_IRQ_SERVICE_8502)/irq.o cfg/8502-irq-probe.cfg
	$(LD65) -C cfg/8502-irq-probe.cfg -o $@ $<

$(IRQ_SERVICE_8502_PRG): $(IRQ_SERVICE_8502_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@

$(BUILD_IRQ_SERVICE_Z80)/irq.rel: bench/irq-service/z80.s | $(BUILD_IRQ_SERVICE_Z80)
	$(SDASZ80) -o $@ $<

$(IRQ_SERVICE_Z80_IHX): $(BUILD_IRQ_SERVICE_Z80)/irq.rel
	$(SDCC) -mz80 --no-std-crt0 --code-loc 0x2800 \
		-o $@ $^

$(IRQ_SERVICE_Z80_BIN): $(IRQ_SERVICE_Z80_IHX) tools/ihx_to_bin.py
	$(PYTHON) tools/ihx_to_bin.py --start 0x2800 --end 0x3000 $< $@

$(BUILD_IRQ_SERVICE_Z80)/launcher.o: bench/irq-service/z80-launcher.s \
		$(IRQ_SERVICE_Z80_BIN) | $(BUILD_IRQ_SERVICE_Z80)
	$(CA65) --cpu 6502 -o $@ $<

$(IRQ_SERVICE_Z80_LAUNCH_BIN): $(BUILD_IRQ_SERVICE_Z80)/launcher.o \
		cfg/8502-z80-irq-launcher.cfg
	$(LD65) -C cfg/8502-z80-irq-launcher.cfg -o $@ $<

$(IRQ_SERVICE_Z80_PRG): $(IRQ_SERVICE_Z80_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x27d0 $< $@

$(BUILD_CONTEXT_8502)/context.o: bench/context/8502.s | $(BUILD_CONTEXT_8502)
	$(CA65) --cpu 6502 -o $@ $<

$(CONTEXT_8502_BIN): $(BUILD_CONTEXT_8502)/context.o cfg/8502-irq-probe.cfg
	$(LD65) -C cfg/8502-irq-probe.cfg -o $@ $<

$(CONTEXT_8502_PRG): $(CONTEXT_8502_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@

$(BUILD_CONTEXT_Z80)/context.rel: bench/context/z80.s | $(BUILD_CONTEXT_Z80)
	$(SDASZ80) -o $@ $<

$(CONTEXT_Z80_IHX): $(BUILD_CONTEXT_Z80)/context.rel
	$(SDCC) -mz80 --no-std-crt0 --code-loc 0x2800 \
		-o $@ $^

$(CONTEXT_Z80_BIN): $(CONTEXT_Z80_IHX) tools/ihx_to_bin.py
	$(PYTHON) tools/ihx_to_bin.py --start 0x2800 --end 0x3000 $< $@

$(BUILD_CONTEXT_Z80)/launcher.o: bench/context/z80-launcher.s \
		$(CONTEXT_Z80_BIN) | $(BUILD_CONTEXT_Z80)
	$(CA65) --cpu 6502 -o $@ $<

$(CONTEXT_Z80_LAUNCH_BIN): $(BUILD_CONTEXT_Z80)/launcher.o \
		cfg/8502-z80-irq-launcher.cfg
	$(LD65) -C cfg/8502-z80-irq-launcher.cfg -o $@ $<

$(CONTEXT_Z80_PRG): $(CONTEXT_Z80_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x27d0 $< $@

$(BUILD_KERNEL_8502)/main.s: bench/kernel/8502/main.c \
		bench/kernel/include/udeks/kernel_bench.h | $(BUILD_KERNEL_8502)
	$(CC65) $(CFLAGS_8502) -I bench/kernel/include -o $@ $<

$(BUILD_KERNEL_8502)/runner.s: bench/kernel/common/runner.c \
		bench/kernel/include/udeks/kernel_bench.h | $(BUILD_KERNEL_8502)
	$(CC65) $(CFLAGS_8502) -I bench/kernel/include -o $@ $<

$(BUILD_KERNEL_8502)/workloads.s: bench/kernel/common/workloads.c \
		bench/kernel/include/udeks/kernel_bench.h | $(BUILD_KERNEL_8502)
	$(CC65) $(CFLAGS_8502) -I bench/kernel/include -o $@ $<

$(BUILD_KERNEL_8502)/%.o: $(BUILD_KERNEL_8502)/%.s | $(BUILD_KERNEL_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_KERNEL_8502)/crt0.o: bench/kernel/8502/crt0.s | $(BUILD_KERNEL_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_KERNEL_8502)/io.o: bench/kernel/8502/io.s | $(BUILD_KERNEL_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_KERNEL_8502)/timer.o: bench/8502/timer.s | $(BUILD_KERNEL_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(KERNEL_8502_BIN): $(BUILD_KERNEL_8502)/crt0.o \
		$(BUILD_KERNEL_8502)/timer.o $(BUILD_KERNEL_8502)/io.o \
		$(BUILD_KERNEL_8502)/main.o $(BUILD_KERNEL_8502)/runner.o \
		$(BUILD_KERNEL_8502)/workloads.o cfg/8502-bootstrap.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-bootstrap.cfg \
		-m $(BUILD_KERNEL_8502)/kernel-8502.map -o $@ $(filter %.o,$^)

$(KERNEL_8502_PRG): $(KERNEL_8502_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2000 $< $@

$(BUILD_KERNEL_Z80)/main.rel: bench/kernel/z80/main.c \
		bench/kernel/include/udeks/kernel_bench.h | $(BUILD_KERNEL_Z80)
	$(SDCC) $(CFLAGS_Z80) -I bench/kernel/include -c -o $@ $<

$(BUILD_KERNEL_Z80)/runner.rel: bench/kernel/common/runner.c \
		bench/kernel/include/udeks/kernel_bench.h | $(BUILD_KERNEL_Z80)
	$(SDCC) $(CFLAGS_Z80) -I bench/kernel/include -c -o $@ $<

$(BUILD_KERNEL_Z80)/workloads.rel: bench/kernel/common/workloads.c \
		bench/kernel/include/udeks/kernel_bench.h | $(BUILD_KERNEL_Z80)
	$(SDCC) $(CFLAGS_Z80) -I bench/kernel/include -c -o $@ $<

$(BUILD_KERNEL_Z80)/crt0.rel: bench/kernel/z80/crt0.s | $(BUILD_KERNEL_Z80)
	$(SDASZ80) -o $@ $<

$(BUILD_KERNEL_Z80)/io.rel: bench/kernel/z80/io.s | $(BUILD_KERNEL_Z80)
	$(SDASZ80) -o $@ $<

$(BUILD_KERNEL_Z80)/timer.rel: bench/z80/timer.s | $(BUILD_KERNEL_Z80)
	$(SDASZ80) -o $@ $<

$(KERNEL_Z80_IHX): $(BUILD_KERNEL_Z80)/crt0.rel \
		$(BUILD_KERNEL_Z80)/timer.rel $(BUILD_KERNEL_Z80)/io.rel \
		$(BUILD_KERNEL_Z80)/main.rel $(BUILD_KERNEL_Z80)/runner.rel \
		$(BUILD_KERNEL_Z80)/workloads.rel
	$(SDCC) $(LDFLAGS_Z80) -o $@ $^

$(KERNEL_Z80_BIN): $(KERNEL_Z80_IHX) tools/ihx_to_bin.py
	$(PYTHON) tools/ihx_to_bin.py --start 0x2000 --end 0x4000 $< $@

$(BUILD_KERNEL_Z80)/launcher.o: bench/kernel/z80/launcher.s \
		$(KERNEL_Z80_BIN) | $(BUILD_KERNEL_Z80)
	$(CA65) --cpu 6502 -o $@ $<

$(KERNEL_Z80_LAUNCH_BIN): $(BUILD_KERNEL_Z80)/launcher.o \
		cfg/8502-z80-launcher.cfg
	$(LD65) -C cfg/8502-z80-launcher.cfg -o $@ $<

$(KERNEL_Z80_PRG): $(KERNEL_Z80_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x1fe0 $< $@

$(BUILD_HANDOFF_8502)/handoff.o: bench/handoff/8502.s | $(BUILD_HANDOFF_8502)
	$(CA65) --cpu 6502 -o $@ $<

$(HANDOFF_8502_BIN): $(BUILD_HANDOFF_8502)/handoff.o \
		cfg/8502-handoff-controller.cfg
	$(LD65) -C cfg/8502-handoff-controller.cfg -o $@ $<

$(BUILD_HANDOFF_Z80)/handoff.rel: bench/handoff/z80.s | $(BUILD_HANDOFF_Z80)
	$(SDASZ80) -o $@ $<

$(HANDOFF_Z80_IHX): $(BUILD_HANDOFF_Z80)/handoff.rel
	$(SDCC) -mz80 --no-std-crt0 --code-loc 0x3000 -o $@ $^

$(HANDOFF_Z80_BIN): $(HANDOFF_Z80_IHX) tools/ihx_to_bin.py
	$(PYTHON) tools/ihx_to_bin.py --start 0x3000 --end 0x3800 $< $@

$(BUILD_HANDOFF_8502)/launcher.o: bench/handoff/launcher.s \
		$(HANDOFF_8502_BIN) $(HANDOFF_Z80_BIN) | $(BUILD_HANDOFF_8502)
	$(CA65) --cpu 6502 -o $@ $<

$(HANDOFF_LAUNCH_BIN): $(BUILD_HANDOFF_8502)/launcher.o \
		cfg/8502-z80-handoff-launcher.cfg
	$(LD65) -C cfg/8502-z80-handoff-launcher.cfg -o $@ $<

$(HANDOFF_PRG): $(HANDOFF_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x1c01 $< $@

$(BUILD_OFFLOAD_8502)/offload.o: bench/offload/8502.s | $(BUILD_OFFLOAD_8502)
	$(CA65) --cpu 6502 -o $@ $<

$(OFFLOAD_8502_BIN): $(BUILD_OFFLOAD_8502)/offload.o \
		cfg/8502-handoff-controller.cfg
	$(LD65) -C cfg/8502-handoff-controller.cfg -o $@ $<

$(BUILD_OFFLOAD_Z80)/offload.rel: bench/offload/z80.s | $(BUILD_OFFLOAD_Z80)
	$(SDASZ80) -o $@ $<

$(OFFLOAD_Z80_IHX): $(BUILD_OFFLOAD_Z80)/offload.rel
	$(SDCC) -mz80 --no-std-crt0 --code-loc 0x3000 -o $@ $^

$(OFFLOAD_Z80_BIN): $(OFFLOAD_Z80_IHX) tools/ihx_to_bin.py
	$(PYTHON) tools/ihx_to_bin.py --start 0x3000 --end 0x3800 $< $@

$(BUILD_OFFLOAD_8502)/launcher.o: bench/offload/launcher.s \
		$(OFFLOAD_8502_BIN) $(OFFLOAD_Z80_BIN) | $(BUILD_OFFLOAD_8502)
	$(CA65) --cpu 6502 -o $@ $<

$(OFFLOAD_LAUNCH_BIN): $(BUILD_OFFLOAD_8502)/launcher.o \
		cfg/8502-z80-handoff-launcher.cfg
	$(LD65) -C cfg/8502-z80-handoff-launcher.cfg -o $@ $<

$(OFFLOAD_PRG): $(OFFLOAD_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x1c01 $< $@

$(BUILD_MEMORY_MAP)/gateway.o: bench/memory-map/gateway.s | $(BUILD_MEMORY_MAP)
	$(CA65) --cpu 6502 -o $@ $<

$(MEMORY_MAP_GATEWAY_BIN): $(BUILD_MEMORY_MAP)/gateway.o \
		cfg/8502-common-gateway.cfg
	$(LD65) -C cfg/8502-common-gateway.cfg -o $@ $<

$(BUILD_MEMORY_MAP)/launcher.o: bench/memory-map/launcher.s \
		$(MEMORY_MAP_GATEWAY_BIN) | $(BUILD_MEMORY_MAP)
	$(CA65) --cpu 6502 -o $@ $<

$(MEMORY_MAP_LAUNCH_BIN): $(BUILD_MEMORY_MAP)/launcher.o \
		cfg/8502-memory-map-probe.cfg
	$(LD65) -C cfg/8502-memory-map-probe.cfg -o $@ $<

$(MEMORY_MAP_PRG): $(MEMORY_MAP_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@

check:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	$(PYTHON) -m py_compile tools/ihx_to_bin.py tools/bin_to_prg.py \
		tools/bench_decode.py tools/irq_probe_decode.py \
		tools/irq_service_decode.py tools/context_decode.py \
		tools/kernel_decode.py tools/handoff_decode.py \
		tools/offload_decode.py tools/boot_status_decode.py \
		tools/memory_map_decode.py \
		tools/snapshot_extract.py \
		tools/vice_capture.py
	cd bench/artifacts/2026-09-24 && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-r2 && sha256sum -c SHA256SUMS
	cd bench/results/vice-3.10-2026-09-24-r1/raw && sha256sum -c SHA256SUMS
	cd bench/results/vice-3.10-2026-09-24-r2/raw && sha256sum -c SHA256SUMS
	cd bench/results/vice-3.10-2026-09-24-r2/repeats && sha256sum -c SHA256SUMS
	cd bench/results/1986-7556c23-2026-09-24-r2/raw && sha256sum -c SHA256SUMS
	cd bench/results/1986-7556c23-2026-09-24-r2/repeats && sha256sum -c SHA256SUMS
	cd bench/results/1986-7556c23-2026-09-24-r2/diagnostics && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-memory-map-smoke/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-memory-map-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-memory-map-profiles/raw && sha256sum -c SHA256SUMS

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
		'make bench      Build comparable 8502 and Z80 benchmark images' \
		'make bench-8502 Build only the 8502 benchmark image' \
		'make bench-z80  Build only the Z80 benchmark image' \
		'make bench-irq  Build the 8502 and Z80 interrupt qualification probes' \
		'make bench-irq-service  Build the instrumented interrupt-service suite' \
		'make bench-context  Build the task-context save/restore suite' \
		'make bench-kernel  Build the syscall, queue, MMU, and device suite' \
		'make bench-handoff  Build the bidirectional ownership/mailbox suite' \
		'make bench-offload  Build the dual-CPU offload crossover sweep' \
		'make bench-memory-map  Build the native MMU profile/relocation probe' \
		'make check      Run host-side tests' \
		'make doctor     Report missing build tools' \
		'make clean      Remove generated build artifacts'
