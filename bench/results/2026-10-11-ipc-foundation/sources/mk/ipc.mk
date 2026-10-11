# SPDX-License-Identifier: GPL-3.0-or-later
IPC_OBJECTS := $(BUILD_8502)/ipc.o
$(BUILD_8502)/ipc.o: src/kernel/ipc.s | $(BUILD_8502)
	$(CA65) --cpu 6502 -o $@ $<
.PHONY: ipc-check ipc-fixture ipc-probe ipc-layout-check
ipc-layout-check: $(KERNEL_BIN) $(PANIC_PROBE_KERNEL_BIN)
	$(PYTHON) tools/ipc_layout.py
ipc-check:
	$(PYTHON) tools/check_ipc.py
ipc-fixture:
	$(PYTHON) tools/build_native_console.py --source bench/ipc/native.c --name IPCTEST --output build/ipc/native \
		--export _ipc_phase --export _ipc_failure --export _ipc_release --export _ipc_handle --export _ipc_peer
ipc-probe:
	$(PYTHON) tools/ipc_probe.py --format d81
	$(PYTHON) tools/ipc_probe.py --format d64
