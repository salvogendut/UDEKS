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
BUILD_CONTEXT_SWITCH := $(BUILD_DIR)/bench/context-switch
BUILD_KERNEL_8502 := $(BUILD_DIR)/bench/kernel/8502
BUILD_KERNEL_Z80 := $(BUILD_DIR)/bench/kernel/z80
BUILD_HANDOFF_8502 := $(BUILD_DIR)/bench/handoff/8502
BUILD_HANDOFF_Z80 := $(BUILD_DIR)/bench/handoff/z80
BUILD_OFFLOAD_8502 := $(BUILD_DIR)/bench/offload/8502
BUILD_OFFLOAD_Z80 := $(BUILD_DIR)/bench/offload/z80
BUILD_MEMORY_MAP := $(BUILD_DIR)/bench/memory-map
BUILD_BOOT := $(BUILD_DIR)/boot
BUILD_ASSETS := $(BUILD_DIR)/assets
BUILD_USER := $(BUILD_DIR)/user

KERNEL_BIN := $(BUILD_8502)/udeks-8502.bin
KERNEL_PRG := $(BUILD_8502)/udeks-8502.prg
MODULE_BIN := $(BUILD_8502)/udeks-module.bin
PANIC_PROBE_KERNEL_BIN := $(BUILD_8502)/udeks-8502-panic-probe.bin
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
CONTEXT_SWITCH_GATEWAY_BIN := $(BUILD_CONTEXT_SWITCH)/gateway.bin
CONTEXT_SWITCH_LAUNCH_BIN := $(BUILD_CONTEXT_SWITCH)/context-switch.bin
CONTEXT_SWITCH_PRG := $(BUILD_CONTEXT_SWITCH)/context-switch.prg
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
STAGE0_BIN := $(BUILD_BOOT)/stage0.bin
STAGE1_GATEWAY_BIN := $(BUILD_BOOT)/stage1-gateway.bin
TASK_LOADER_BIN := $(BUILD_BOOT)/task-loader.bin
TASK_REQUEST_GATE_BIN := $(BUILD_BOOT)/task-request-gateway.bin
BOOTFS_REQUEST_SERVICE_BIN := $(BUILD_BOOT)/bootfs-request-service.bin
TASK_BANK_GATE_BIN := $(BUILD_BOOT)/task-bank-gateway.bin
STAGE1_BIN := $(BUILD_BOOT)/stage1.bin
BOOT_D71 := $(BUILD_BOOT)/udeks.d71
BOOT_D64 := $(BUILD_BOOT)/udeks.d64
PANIC_PROBE_D71 := $(BUILD_BOOT)/udeks-panic-probe.d71
VDC_SPLASH_BIN := $(BUILD_ASSETS)/udekspipe-64.vdc
VDC_WORDMARK_BIN := $(BUILD_ASSETS)/udekusu-64.vdc
VDC_TEXT_ASSETS_BIN := $(BUILD_ASSETS)/udeks-vdc-text.bin
VIC_BUSY_SPRITE_BIN := $(BUILD_ASSETS)/24x21-pipe-sprite.vic
USER_COWSAY_ASM := $(BUILD_USER)/cowsay.s
USER_COWSAY_OBJ := $(BUILD_USER)/cowsay.o
USER_DATE_ASM := $(BUILD_USER)/date.s
USER_DATE_OBJ := $(BUILD_USER)/date.o
USER_LS_ASM := $(BUILD_USER)/ls.s
USER_LS_OBJ := $(BUILD_USER)/ls.o
USER_ENTRY_OBJ := $(BUILD_USER)/entry.o
USER_SYSCALL_OBJ := $(BUILD_USER)/syscall.o
USER_TASK_STREAM_ASM := $(BUILD_USER)/task_stream.s
USER_TASK_STREAM_OBJ := $(BUILD_USER)/task_stream.o
USER_FILESYSTEM_ASM := $(BUILD_USER)/filesystem.s
USER_FILESYSTEM_OBJ := $(BUILD_USER)/filesystem.o
USER_POLL_ENTRY_OBJ := $(BUILD_USER)/poll_entry.o
USER_USH_ASM := $(BUILD_USER)/ush.s
USER_USH_OBJ := $(BUILD_USER)/ush.o
USER_COWSAY_BIN := $(BUILD_USER)/cowsay.bin
USER_COWSAY_UDEX := $(BUILD_USER)/cowsay.udx
USER_DATE_BIN := $(BUILD_USER)/date.bin
USER_DATE_UDEX := $(BUILD_USER)/date.udx
USER_LS_BIN := $(BUILD_USER)/ls.bin
USER_LS_UDEX := $(BUILD_USER)/ls.udx
USER_USH_BIN := $(BUILD_USER)/ush.bin
USER_USH_UDEX := $(BUILD_USER)/ush.udx
USER_APP_IMPORTS_OBJ := $(BUILD_USER)/app_imports.o
USER_XCLOCK_ASM := $(BUILD_USER)/xclock.s
USER_XCLOCK_OBJ := $(BUILD_USER)/xclock.o
USER_XCLOCK_ENTRY_OBJ := $(BUILD_USER)/xclock_entry.o
USER_XCLOCK_BIN := $(BUILD_USER)/xclock.bin
USER_XCLOCK_UDEX := $(BUILD_USER)/xclock.udx
USER_XWAVE_ASM := $(BUILD_USER)/xwave.s
USER_XWAVE_OBJ := $(BUILD_USER)/xwave.o
USER_XWAVE_ENTRY_OBJ := $(BUILD_USER)/xwave_entry.o
USER_XWAVE_BIN := $(BUILD_USER)/xwave.bin
USER_XWAVE_UDEX := $(BUILD_USER)/xwave.udx
USER_BOOTFS := $(BUILD_USER)/bootfs.img

.PHONY: all 8502 z80 z80-asm bench bench-8502 bench-z80 bench-irq \
	bench-irq-8502 bench-irq-z80 bench-irq-service \
	bench-irq-service-8502 bench-irq-service-z80 bench-context \
	bench-context-8502 bench-context-z80 bench-context-switch \
	bench-kernel bench-kernel-8502 \
	bench-kernel-z80 bench-handoff bench-offload bench-memory-map \
	boot panic-probe framebuffer-assets user-sources user-programs \
	task-state check doctor clean help

all: 8502 z80 z80-asm

boot: $(BOOT_D71) $(BOOT_D64)

panic-probe: $(PANIC_PROBE_D71)

framebuffer-assets: $(VDC_SPLASH_BIN) $(VDC_WORDMARK_BIN) \
		$(VDC_TEXT_ASSETS_BIN) $(VIC_BUSY_SPRITE_BIN)

# Compile user programs independently; they must never enter the resident link.
user-sources: $(USER_COWSAY_ASM) $(USER_DATE_ASM) $(USER_LS_ASM) $(USER_USH_ASM) \
		$(USER_XCLOCK_ASM) $(USER_XWAVE_ASM) $(USER_TASK_STREAM_OBJ) \
		$(USER_FILESYSTEM_OBJ) $(USER_POLL_ENTRY_OBJ)

user-programs: $(USER_BOOTFS)

# Compile-only proof that the host-tested lifecycle module builds for cc65.
task-state: $(BUILD_8502)/task_state.o

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

bench-context-switch: $(CONTEXT_SWITCH_PRG)

bench-kernel: bench-kernel-8502 bench-kernel-z80

bench-kernel-8502: $(KERNEL_8502_BIN) $(KERNEL_8502_PRG)

bench-kernel-z80: $(KERNEL_Z80_BIN) $(KERNEL_Z80_PRG)

bench-handoff: $(HANDOFF_PRG)

bench-offload: $(OFFLOAD_PRG)

bench-memory-map: $(MEMORY_MAP_PRG)

$(BUILD_8502) $(BUILD_Z80) $(BUILD_BENCH_8502) $(BUILD_BENCH_Z80) \
		$(BUILD_IRQ_8502) $(BUILD_IRQ_Z80) $(BUILD_IRQ_SERVICE_8502) \
		$(BUILD_IRQ_SERVICE_Z80) $(BUILD_CONTEXT_8502) $(BUILD_CONTEXT_Z80) \
		$(BUILD_CONTEXT_SWITCH) \
		$(BUILD_KERNEL_8502) $(BUILD_KERNEL_Z80) $(BUILD_HANDOFF_8502) \
		$(BUILD_HANDOFF_Z80) $(BUILD_OFFLOAD_8502) $(BUILD_OFFLOAD_Z80) \
		$(BUILD_MEMORY_MAP) $(BUILD_BOOT) $(BUILD_ASSETS) $(BUILD_USER):
	mkdir -p $@

$(USER_COWSAY_ASM): user/bin/cowsay.c user/include/udeks/program.h | $(BUILD_USER)
	$(CC65) $(CFLAGS_8502) -I user/include -o $@ $<

$(USER_COWSAY_OBJ): $(USER_COWSAY_ASM) | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_DATE_ASM): user/bin/date.c user/include/udeks/program.h \
		include/udeks/time.h | $(BUILD_USER)
	$(CC65) $(CFLAGS_8502) -I user/include -I include -o $@ $<

$(USER_DATE_OBJ): $(USER_DATE_ASM) | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_LS_ASM): user/bin/ls.c user/include/udeks/program.h \
		include/udeks/task_request.h | $(BUILD_USER)
	$(CC65) $(CFLAGS_8502) -I user/include -I include -o $@ $<

$(USER_LS_OBJ): $(USER_LS_ASM) | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_ENTRY_OBJ): user/lib/entry.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_SYSCALL_OBJ): user/lib/syscall.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_TASK_STREAM_ASM): user/lib/task_stream.c user/include/udeks/program.h \
		include/udeks/task_bank.h include/udeks/task_request.h | $(BUILD_USER)
	$(CC65) $(CFLAGS_8502) -I user/include -I include -o $@ $<

$(USER_TASK_STREAM_OBJ): $(USER_TASK_STREAM_ASM) | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_FILESYSTEM_ASM): user/lib/filesystem.c user/include/udeks/program.h \
		include/udeks/syscall.h include/udeks/task_request.h | $(BUILD_USER)
	$(CC65) $(CFLAGS_8502) -I user/include -I include -o $@ $<

$(USER_FILESYSTEM_OBJ): $(USER_FILESYSTEM_ASM) | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_POLL_ENTRY_OBJ): user/lib/poll_entry.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_USH_ASM): user/bin/ush.c user/include/udeks/program.h \
		include/udeks/memory.h include/udeks/task_request.h | $(BUILD_USER)
	$(CC65) $(CFLAGS_8502) -I user/include -I include -o $@ $<

$(USER_USH_OBJ): $(USER_USH_ASM) | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_COWSAY_BIN): $(USER_ENTRY_OBJ) $(USER_SYSCALL_OBJ) \
		$(USER_COWSAY_OBJ) cfg/8502-user-app1.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-user-app1.cfg \
		-m $(BUILD_USER)/cowsay.map -o $@ $(filter %.o,$^)

$(USER_COWSAY_UDEX): $(USER_COWSAY_BIN) tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 \
		--entry-address 0x0200 $< $@

$(USER_DATE_BIN): $(USER_ENTRY_OBJ) $(USER_SYSCALL_OBJ) \
		$(USER_DATE_OBJ) cfg/8502-user-app1.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-user-app1.cfg \
		-m $(BUILD_USER)/date.map -o $@ $(filter %.o,$^)

$(USER_DATE_UDEX): $(USER_DATE_BIN) tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 \
		--entry-address 0x0200 $< $@

$(USER_LS_BIN): $(USER_ENTRY_OBJ) $(USER_SYSCALL_OBJ) $(USER_FILESYSTEM_OBJ) \
		$(USER_LS_OBJ) cfg/8502-user-app1.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-user-app1.cfg \
		-m $(BUILD_USER)/ls.map -o $@ $(filter %.o,$^)

$(USER_LS_UDEX): $(USER_LS_BIN) tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 \
		--entry-address 0x0200 $< $@

$(USER_USH_BIN): $(USER_POLL_ENTRY_OBJ) $(USER_TASK_STREAM_OBJ) \
		$(USER_USH_OBJ) cfg/8502-user-bank1.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-user-bank1.cfg \
		-m $(BUILD_USER)/ush.map -o $@ $(filter %.o,$^)

$(USER_USH_UDEX): $(USER_USH_BIN) tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x9000 \
		--entry-address 0x9000 --bss-size 0x0050 --flags 0x01 $< $@

$(USER_APP_IMPORTS_OBJ): user/lib/app_imports.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_XCLOCK_ASM): src/apps/xclock.c include/udeks/time.h \
		include/udeks/vic_graphics.h include/udeks/window.h \
		include/udeks/xclock.h | $(BUILD_USER)
	$(CC65) $(CFLAGS_8502) -I include -o $@ $<

$(USER_XCLOCK_OBJ): $(USER_XCLOCK_ASM) | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_XCLOCK_ENTRY_OBJ): user/lib/xclock_entry.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_XCLOCK_BIN): $(USER_XCLOCK_ENTRY_OBJ) $(USER_XCLOCK_OBJ) \
		$(USER_APP_IMPORTS_OBJ) cfg/8502-managed-app1.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-managed-app1.cfg \
		-m $(BUILD_USER)/xclock.map -o $@ $(filter %.o,$^)

$(USER_XCLOCK_UDEX): $(USER_XCLOCK_BIN) tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 \
		--entry-address 0x0200 --bss-size 0x000D --flags 0x02 $< $@

$(USER_XWAVE_ASM): src/apps/xwave.c include/udeks/mailbox.h \
		include/udeks/vic_graphics.h include/udeks/window.h \
		include/udeks/xwave.h include/udeks/z80_worker.h | $(BUILD_USER)
	$(CC65) $(CFLAGS_8502) -I include -o $@ $<

$(USER_XWAVE_OBJ): $(USER_XWAVE_ASM) | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_XWAVE_ENTRY_OBJ): user/lib/xwave_entry.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<

$(USER_XWAVE_BIN): $(USER_XWAVE_ENTRY_OBJ) $(USER_XWAVE_OBJ) \
		$(USER_APP_IMPORTS_OBJ) cfg/8502-managed-app2.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-managed-app2.cfg \
		-m $(BUILD_USER)/xwave.map -o $@ $(filter %.o,$^)

$(USER_XWAVE_UDEX): $(USER_XWAVE_BIN) tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x1200 \
		--entry-address 0x1200 --bss-size 0x0218 --flags 0x02 $< $@

$(USER_BOOTFS): $(USER_COWSAY_UDEX) $(USER_DATE_UDEX) $(USER_LS_UDEX) \
		$(USER_USH_UDEX) $(USER_XCLOCK_UDEX) $(USER_XWAVE_UDEX) \
		tools/build_bootfs.py
	$(PYTHON) tools/build_bootfs.py --max-size 0x2DBB \
		--entry cowsay=$(USER_COWSAY_UDEX) \
		--entry date=$(USER_DATE_UDEX) \
		--entry ls=$(USER_LS_UDEX) \
		--entry ush=$(USER_USH_UDEX) \
		--entry xclock=$(USER_XCLOCK_UDEX) \
		--entry xwave=$(USER_XWAVE_UDEX) $@

$(VDC_SPLASH_BIN): assets/udekspipe-64.xpm tools/xpm_to_vdc.py | $(BUILD_ASSETS)
	$(PYTHON) tools/xpm_to_vdc.py $< $@

$(VDC_WORDMARK_BIN): assets/udekusu-64.xpm tools/xpm_to_vdc.py | $(BUILD_ASSETS)
	$(PYTHON) tools/xpm_to_vdc.py $< $@

$(VDC_TEXT_ASSETS_BIN): assets/udekspipe-64.xpm assets/udekusu-64.xpm \
		tools/xpm_to_vdc.py tools/xpm_to_vdc_text.py | $(BUILD_ASSETS)
	$(PYTHON) tools/xpm_to_vdc_text.py \
		assets/udekspipe-64.xpm assets/udekusu-64.xpm $@

$(VIC_BUSY_SPRITE_BIN): assets/24x21-pipe-sprite.png \
		tools/png_to_vic_sprite.py | $(BUILD_ASSETS)
	$(PYTHON) tools/png_to_vic_sprite.py $< $@

$(BUILD_8502)/kernel.s: src/8502/kernel.c include/udeks/mailbox.h \
		include/udeks/memory.h include/udeks/panic.h include/udeks/compiler.h \
		include/udeks/service.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/service_registry.s: src/kernel/service_registry.c \
		include/udeks/service.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/task_state.s: src/kernel/task_state.c \
		include/udeks/task_state.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/hardware_capability.s: src/services/capability/hardware.c \
		include/udeks/capability.h include/udeks/vdc.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/time.s: src/services/time/time.c include/udeks/capability.h \
		include/udeks/time.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/vdc_console.s: src/services/console/vdc_console.c \
		include/udeks/boot_console.h include/udeks/compiler.h \
		include/udeks/console.h include/udeks/root_console.h \
		include/udeks/theme.h include/udeks/vdc.h \
		include/udeks/vic_graphics.h include/udeks/xclock.h \
		include/udeks/xwave.h \
		| $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/vdc_framebuffer.s: src/services/framebuffer/vdc_framebuffer.c \
		include/udeks/boot_console.h include/udeks/capability.h \
		include/udeks/font.h include/udeks/framebuffer.h \
		include/udeks/root_console.h include/udeks/theme.h include/udeks/vdc.h \
		| $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/root_console.s: src/services/window/root_console.c \
		include/udeks/root_console.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/window_manager.s: src/services/window/window_manager.c \
		include/udeks/pointer.h include/udeks/vic_graphics.h \
		include/udeks/window.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/boot_console.s: src/services/window/boot_console.c \
		include/udeks/boot_console.h include/udeks/capability.h \
		include/udeks/root_console.h include/udeks/z80_worker.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/keyboard.s: src/services/input/keyboard.c \
		include/udeks/keyboard.h include/udeks/pointer.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/joystick.s: src/services/input/joystick.c \
		include/udeks/joystick.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/mouse1351.s: src/services/input/mouse1351.c \
		include/udeks/mouse1351.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/line_editor.s: src/services/terminal/line_editor.c \
		include/udeks/keyboard.h include/udeks/line_editor.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/root_terminal.s: src/services/terminal/root_terminal.c \
		include/udeks/console.h include/udeks/keyboard.h \
		include/udeks/line_editor.h include/udeks/root_console.h \
		include/udeks/root_terminal.h include/udeks/shell.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/terminal_stream.s: src/services/terminal/stream.c \
		include/udeks/root_console.h include/udeks/stream.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/shell_parser.s: user/lib/shell_parser.c \
		include/udeks/shell.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/shell.s: src/services/shell/shell.c \
		include/udeks/capability.h include/udeks/line_editor.h \
		include/udeks/root_console.h include/udeks/root_terminal.h \
		include/udeks/service.h include/udeks/shell.h \
		include/udeks/stream.h include/udeks/task.h include/udeks/mailbox.h \
		include/udeks/z80_worker.h include/udeks/vic_graphics.h \
		include/udeks/window.h include/udeks/xclock.h \
		include/udeks/xwave.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/z80_worker.s: src/services/engine/z80_worker.c \
		include/udeks/mailbox.h include/udeks/memory.h \
		include/udeks/vic_graphics.h include/udeks/z80_worker.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/vic_graphics.s: src/services/display/vic_graphics.c \
		include/udeks/memory.h include/udeks/pointer.h \
		include/udeks/vic_graphics.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/framebuffer_font.s: src/services/framebuffer/font.c \
		include/udeks/font.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/framebuffer_surface.s: src/services/framebuffer/surface.c \
		include/udeks/font.h include/udeks/framebuffer.h \
		include/udeks/framebuffer_surface.h | $(BUILD_8502)
	$(CC65) $(CFLAGS_8502) -o $@ $<

$(BUILD_8502)/kernel.o: $(BUILD_8502)/kernel.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/vdc_console.o: $(BUILD_8502)/vdc_console.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/vdc_framebuffer.o: $(BUILD_8502)/vdc_framebuffer.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/root_console.o: $(BUILD_8502)/root_console.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/window_manager.o: $(BUILD_8502)/window_manager.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/boot_console.o: $(BUILD_8502)/boot_console.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/keyboard.o: $(BUILD_8502)/keyboard.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/joystick.o: $(BUILD_8502)/joystick.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/mouse1351.o: $(BUILD_8502)/mouse1351.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/pointer.o: src/8502/pointer_irq.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/line_editor.o: $(BUILD_8502)/line_editor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/root_terminal.o: $(BUILD_8502)/root_terminal.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/terminal_stream.o: $(BUILD_8502)/terminal_stream.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/shell_parser.o: $(BUILD_8502)/shell_parser.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/shell.o: $(BUILD_8502)/shell.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/z80_worker.o: $(BUILD_8502)/z80_worker.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/vic_graphics.o: $(BUILD_8502)/vic_graphics.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/managed_apps.o: src/services/app/managed_apps.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/app_panel.o: src/services/console/app_panel.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/framebuffer_font.o: $(BUILD_8502)/framebuffer_font.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/framebuffer_surface.o: $(BUILD_8502)/framebuffer_surface.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/service_registry.o: $(BUILD_8502)/service_registry.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/task_state.o: $(BUILD_8502)/task_state.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/hardware_capability.o: $(BUILD_8502)/hardware_capability.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/time.o: $(BUILD_8502)/time.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/bootfs_request.o: src/services/filesystem/bootfs_request.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/clock.o: src/8502/clock.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/syscall_gate.o: src/8502/syscall_gate.s src/8502/app_gateway.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/task_bank_gateway.o: src/8502/task_bank_gateway.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/capability_descriptor.o: src/services/capability/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/time_descriptor.o: src/services/time/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/clock_descriptor.o: src/services/clock/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/console_descriptor.o: src/services/console/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/console_descriptor_fault.o: src/services/console/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -D UDEKS_FAULT_SERVICE_MAGIC -o $@ $<

$(BUILD_8502)/framebuffer_descriptor.o: src/services/framebuffer/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/keyboard_descriptor.o: src/services/input/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/pointer_descriptor.o: src/services/input/pointer_descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/root_terminal_descriptor.o: src/services/terminal/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/shell_descriptor.o: src/services/shell/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/init_descriptor.o: src/services/init/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/z80_worker_descriptor.o: src/services/engine/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/vic_graphics_descriptor.o: src/services/display/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/window_descriptor.o: src/services/window/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/managed_apps_descriptor.o: src/services/app/descriptor.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/vdc_splash.o: src/assets/vdc_splash.s $(VDC_SPLASH_BIN) \
		$(VDC_WORDMARK_BIN) | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/vdc_text_assets.o: src/assets/vdc_text_assets.s \
		$(VDC_TEXT_ASSETS_BIN) | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/service_table.o: src/services/table.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/crt0.o: src/8502/crt0.s src/8502/mmu.inc | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/vdc.o: src/8502/vdc.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/panic.o: src/8502/panic.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/probe.o: src/8502/probe.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/keyboard_scan.o: src/8502/keyboard_scan.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/control_ports.o: src/8502/control_ports.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/line_editor_read.o: src/8502/line_editor_read.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/z80_handoff.o: src/8502/z80_handoff.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(BUILD_8502)/vic_graphics_transport.o: src/8502/vic_graphics.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -o $@ $<

$(KERNEL_BIN): $(BUILD_8502)/crt0.o $(BUILD_8502)/vdc.o \
		$(BUILD_8502)/keyboard_scan.o $(BUILD_8502)/control_ports.o \
		$(BUILD_8502)/line_editor_read.o \
		$(BUILD_8502)/z80_handoff.o \
		$(BUILD_8502)/vic_graphics_transport.o \
		$(BUILD_8502)/panic.o $(BUILD_8502)/probe.o $(BUILD_8502)/clock.o \
		$(BUILD_8502)/syscall_gate.o \
		$(BUILD_8502)/task_bank_gateway.o \
		$(BUILD_8502)/kernel.o $(BUILD_8502)/service_registry.o \
		$(BUILD_8502)/service_table.o \
		$(BUILD_8502)/capability_descriptor.o \
		$(BUILD_8502)/time_descriptor.o \
		$(BUILD_8502)/clock_descriptor.o \
		$(BUILD_8502)/console_descriptor.o \
		$(BUILD_8502)/pointer_descriptor.o \
		$(BUILD_8502)/keyboard_descriptor.o \
		$(BUILD_8502)/root_terminal_descriptor.o \
		$(BUILD_8502)/init_descriptor.o \
		$(BUILD_8502)/z80_worker_descriptor.o \
		$(BUILD_8502)/vic_graphics_descriptor.o \
		$(BUILD_8502)/window_descriptor.o \
		$(BUILD_8502)/managed_apps_descriptor.o \
		$(BUILD_8502)/bootfs_request.o \
		$(BUILD_8502)/hardware_capability.o $(BUILD_8502)/time.o \
		$(BUILD_8502)/vdc_console.o $(BUILD_8502)/app_panel.o \
		$(BUILD_8502)/root_console.o $(BUILD_8502)/window_manager.o \
		$(BUILD_8502)/boot_console.o $(BUILD_8502)/keyboard.o \
		$(BUILD_8502)/pointer.o \
		$(BUILD_8502)/line_editor.o $(BUILD_8502)/root_terminal.o \
		$(BUILD_8502)/terminal_stream.o \
		$(BUILD_8502)/shell_parser.o $(BUILD_8502)/shell.o \
		$(BUILD_8502)/z80_worker.o \
		$(BUILD_8502)/vic_graphics.o \
		$(BUILD_8502)/managed_apps.o \
		$(BUILD_8502)/vdc_text_assets.o \
		cfg/8502-bootstrap.cfg
	$(CL65) -t none --cpu 6502 $(LDFLAGS_8502) -o $@ $(filter %.o,$^)

$(PANIC_PROBE_KERNEL_BIN): $(BOOT_D71) \
		$(BUILD_8502)/crt0.o $(BUILD_8502)/vdc.o \
		$(BUILD_8502)/keyboard_scan.o $(BUILD_8502)/control_ports.o \
		$(BUILD_8502)/line_editor_read.o \
		$(BUILD_8502)/z80_handoff.o \
		$(BUILD_8502)/vic_graphics_transport.o \
		$(BUILD_8502)/panic.o $(BUILD_8502)/probe.o $(BUILD_8502)/clock.o \
		$(BUILD_8502)/syscall_gate.o \
		$(BUILD_8502)/task_bank_gateway.o \
		$(BUILD_8502)/kernel.o $(BUILD_8502)/service_registry.o \
		$(BUILD_8502)/service_table.o $(BUILD_8502)/capability_descriptor.o \
		$(BUILD_8502)/time_descriptor.o \
		$(BUILD_8502)/clock_descriptor.o \
		$(BUILD_8502)/console_descriptor_fault.o \
		$(BUILD_8502)/pointer_descriptor.o \
		$(BUILD_8502)/keyboard_descriptor.o \
		$(BUILD_8502)/root_terminal_descriptor.o \
		$(BUILD_8502)/init_descriptor.o \
		$(BUILD_8502)/z80_worker_descriptor.o \
		$(BUILD_8502)/vic_graphics_descriptor.o \
		$(BUILD_8502)/window_descriptor.o \
		$(BUILD_8502)/managed_apps_descriptor.o \
		$(BUILD_8502)/bootfs_request.o \
		$(BUILD_8502)/hardware_capability.o $(BUILD_8502)/time.o \
		$(BUILD_8502)/vdc_console.o $(BUILD_8502)/app_panel.o \
		$(BUILD_8502)/root_console.o $(BUILD_8502)/window_manager.o \
		$(BUILD_8502)/boot_console.o $(BUILD_8502)/keyboard.o \
		$(BUILD_8502)/pointer.o \
		$(BUILD_8502)/line_editor.o $(BUILD_8502)/root_terminal.o \
		$(BUILD_8502)/terminal_stream.o \
		$(BUILD_8502)/shell_parser.o $(BUILD_8502)/shell.o \
		$(BUILD_8502)/z80_worker.o \
		$(BUILD_8502)/vic_graphics.o \
		$(BUILD_8502)/managed_apps.o \
		$(BUILD_8502)/vdc_text_assets.o \
		cfg/8502-bootstrap.cfg
	$(CL65) -t none --cpu 6502 -C cfg/8502-bootstrap.cfg \
		-m $(BUILD_8502)/udeks-8502-panic-probe.map -o $@ \
		$(filter %.o,$^)

$(KERNEL_PRG): $(KERNEL_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2000 $< $@

$(MODULE_BIN): $(KERNEL_BIN)
	test -s $@

$(TASK_BANK_GATE_BIN): $(KERNEL_BIN)
	test -s $@

$(TASK_REQUEST_GATE_BIN): $(KERNEL_BIN)
	test -s $@

$(BOOTFS_REQUEST_SERVICE_BIN): $(KERNEL_BIN)
	test -s $@

$(BUILD_Z80)/worker.rel: src/z80/worker.c include/udeks/mailbox.h | $(BUILD_Z80)
	$(SDCC) $(CFLAGS_Z80) -c -o $@ $<

$(BUILD_Z80)/handoff.rel: src/z80/handoff.s | $(BUILD_Z80)
	$(SDASZ80) -o $@ $<

$(BUILD_Z80)/crt0.rel: src/z80/crt0.s | $(BUILD_Z80)
	$(SDASZ80) -o $@ $<

$(Z80_IHX): $(BUILD_Z80)/crt0.rel $(BUILD_Z80)/handoff.rel \
		$(BUILD_Z80)/worker.rel
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

$(BUILD_CONTEXT_SWITCH)/gateway.o: bench/context-switch/gateway.s \
		| $(BUILD_CONTEXT_SWITCH)
	$(CA65) --cpu 6502 -o $@ $<

$(CONTEXT_SWITCH_GATEWAY_BIN): $(BUILD_CONTEXT_SWITCH)/gateway.o \
		cfg/8502-common-gateway.cfg
	$(LD65) -C cfg/8502-common-gateway.cfg -o $@ $<

$(BUILD_CONTEXT_SWITCH)/launcher.o: bench/context-switch/launcher.s \
		$(CONTEXT_SWITCH_GATEWAY_BIN) | $(BUILD_CONTEXT_SWITCH)
	$(CA65) --cpu 6502 -o $@ $<

$(CONTEXT_SWITCH_LAUNCH_BIN): $(BUILD_CONTEXT_SWITCH)/launcher.o \
		cfg/8502-context-switch.cfg
	$(LD65) -C cfg/8502-context-switch.cfg -o $@ $<

$(CONTEXT_SWITCH_PRG): $(CONTEXT_SWITCH_LAUNCH_BIN) tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@

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

$(BUILD_BOOT)/stage0.o: src/boot/stage0.s | $(BUILD_BOOT)
	$(CA65) --cpu 6502 -o $@ $<

$(STAGE0_BIN): $(BUILD_BOOT)/stage0.o cfg/8502-stage0.cfg
	$(LD65) -C cfg/8502-stage0.cfg -o $@ $<

$(BUILD_BOOT)/stage1-gateway.o: src/boot/stage1-gateway.s | $(BUILD_BOOT)
	$(CA65) --cpu 6502 -o $@ $<

$(STAGE1_GATEWAY_BIN) $(TASK_LOADER_BIN) &: $(BUILD_BOOT)/stage1-gateway.o \
		cfg/8502-stage1-gateway.cfg
	$(LD65) -C cfg/8502-stage1-gateway.cfg \
		-o $(STAGE1_GATEWAY_BIN) $<

$(BUILD_BOOT)/stage1.o: src/boot/stage1.s $(STAGE1_GATEWAY_BIN) \
		$(VIC_BUSY_SPRITE_BIN) | $(BUILD_BOOT)
	$(CA65) --cpu 6502 -o $@ $<

$(STAGE1_BIN): $(BUILD_BOOT)/stage1.o cfg/8502-stage1.cfg
	$(LD65) -C cfg/8502-stage1.cfg -o $@ $<

$(BOOT_D71) $(BOOT_D64) &: $(STAGE0_BIN) $(STAGE1_BIN) $(KERNEL_BIN) $(MODULE_BIN) \
		$(Z80_BIN) $(USER_BOOTFS) \
		$(USER_USH_UDEX) $(TASK_LOADER_BIN) $(TASK_REQUEST_GATE_BIN) \
		$(BOOTFS_REQUEST_SERVICE_BIN) \
		$(TASK_BANK_GATE_BIN) \
		tools/build_d71.py
	$(PYTHON) tools/build_d71.py --stage0 $(STAGE0_BIN) \
		--stage1 $(STAGE1_BIN) --kernel $(KERNEL_BIN) --z80 $(Z80_BIN) \
		--bootfs $(USER_BOOTFS) \
		--module $(MODULE_BIN) \
		--ush $(USER_USH_UDEX) \
		--task-loader $(TASK_LOADER_BIN) \
		--task-request-gateway $(TASK_REQUEST_GATE_BIN) \
		--bootfs-request-service $(BOOTFS_REQUEST_SERVICE_BIN) \
		--task-bank-gateway $(TASK_BANK_GATE_BIN) \
		--d64-output $(BOOT_D64) $(BOOT_D71)

$(PANIC_PROBE_D71): $(STAGE0_BIN) $(STAGE1_BIN) $(PANIC_PROBE_KERNEL_BIN) \
		$(MODULE_BIN) \
		$(Z80_BIN) $(USER_BOOTFS) \
		$(USER_USH_UDEX) $(TASK_LOADER_BIN) $(TASK_REQUEST_GATE_BIN) \
		$(BOOTFS_REQUEST_SERVICE_BIN) \
		$(TASK_BANK_GATE_BIN) \
		tools/build_d71.py
	$(PYTHON) tools/build_d71.py --stage0 $(STAGE0_BIN) \
		--stage1 $(STAGE1_BIN) --kernel $(PANIC_PROBE_KERNEL_BIN) \
		--z80 $(Z80_BIN) \
		--bootfs $(USER_BOOTFS) \
		--module $(MODULE_BIN) \
		--ush $(USER_USH_UDEX) \
		--task-loader $(TASK_LOADER_BIN) \
		--task-request-gateway $(TASK_REQUEST_GATE_BIN) \
		--bootfs-request-service $(BOOTFS_REQUEST_SERVICE_BIN) \
		--task-bank-gateway $(TASK_BANK_GATE_BIN) $@

check:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	$(PYTHON) -m py_compile tools/ihx_to_bin.py tools/bin_to_prg.py \
		tools/bench_decode.py tools/irq_probe_decode.py \
		tools/irq_service_decode.py tools/context_decode.py \
		tools/context_switch_decode.py \
		tools/kernel_decode.py tools/handoff_decode.py \
		tools/offload_decode.py tools/boot_status_decode.py \
		tools/memory_map_decode.py tools/boot_chain_decode.py \
		tools/vdc_console_decode.py tools/service_registry_decode.py \
		tools/panic_decode.py tools/capability_decode.py \
		tools/framebuffer_decode.py tools/clock_decode.py tools/xpm_to_vdc.py \
		tools/xpm_to_vdc_text.py tools/png_to_vic_sprite.py \
		tools/keyboard_decode.py \
		tools/root_terminal_decode.py \
		tools/z80_worker_decode.py \
		tools/vic_graphics_decode.py \
		tools/pointer_decode.py \
		tools/time_decode.py tools/window_decode.py tools/xclock_decode.py \
		tools/xwave_decode.py \
		tools/build_udex.py \
		tools/build_bootfs.py \
		tools/build_d71.py \
		tools/snapshot_extract.py \
		tools/task_state_decode.py \
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
	cd bench/artifacts/2026-09-26-context-switch-r1 && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-26-context-switch-r2 && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-26-context-switch-r3 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-26-context-switch/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-memory-map-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-memory-map-profiles/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-native-boot-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-native-boot/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-vdc-console-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-vdc-console/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-service-registry-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-service-registry/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-panic-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-panic/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-capabilities-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-capabilities/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-vdc-framebuffer-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-vdc-framebuffer/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-vdc-font-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-vdc-font/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-vdc-pipe-logo-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-vdc-pipe-logo/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-framebuffer-api-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-framebuffer-api/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-reference-bootscreen-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-reference-bootscreen/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-root-console-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-root-console/raw && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-clock-2mhz-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-clock-2mhz/raw && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-clock-2mhz/timing && sha256sum -c SHA256SUMS
	cd bench/artifacts/2026-09-24-atomic-framebuffer-r1 && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-atomic-framebuffer/raw && sha256sum -c SHA256SUMS
	cd bench/results/2026-09-24-atomic-framebuffer/timing && sha256sum -c SHA256SUMS

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
		'make boot       Build the native autoboot D71 image' \
		'make panic-probe  Build the bad-descriptor panic qualification D71' \
		'make framebuffer-assets  Pack the VDC boot-splash source artwork' \
		'make user-sources  Compile staged user-program C sources' \
		'make user-programs  Link and package staged UDEX programs' \
		'make task-state Compile the lifecycle module for cc65 (no link)' \
		'make bench      Build comparable 8502 and Z80 benchmark images' \
		'make bench-8502 Build only the 8502 benchmark image' \
		'make bench-z80  Build only the Z80 benchmark image' \
		'make bench-irq  Build the 8502 and Z80 interrupt qualification probes' \
		'make bench-irq-service  Build the instrumented interrupt-service suite' \
		'make bench-context  Build the task-context save/restore suite' \
		'make bench-context-switch  Build the standalone context-switch spike' \
		'make bench-kernel  Build the syscall, queue, MMU, and device suite' \
		'make bench-handoff  Build the bidirectional ownership/mailbox suite' \
		'make bench-offload  Build the dual-CPU offload crossover sweep' \
		'make bench-memory-map  Build the native MMU profile/relocation probe' \
		'make check      Run host-side tests' \
		'make doctor     Report missing build tools' \
		'make clean      Remove generated build artifacts'
