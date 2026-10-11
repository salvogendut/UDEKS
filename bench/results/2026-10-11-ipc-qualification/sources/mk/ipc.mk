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

.PHONY: ipc-examples
ipc-examples:
	$(PYTHON) tools/build_native_console.py --source user/examples/ipc/server.c --name IPCSRV --output build/ipc/server \
		--export _ipc_server_state --export _ipc_server_error --export _ipc_server_count --export _ipc_server_handle
	$(PYTHON) tools/build_native_console.py --source user/examples/ipc/client.c --name IPCPING --output build/ipc/client \
		--export _ipc_client_state --export _ipc_client_error --export _ipc_client_count --export _ipc_client_reply \
		--export _ipc_client_handle --export _ipc_client_peer

.PHONY: ipc-demo ipc-demo-probe
ipc-demo: boot ipc-examples
	$(PYTHON) tools/build_ipc_demo.py
ipc-demo-probe:
	$(PYTHON) tools/ipc_demo_probe.py --format d71
	$(PYTHON) tools/ipc_demo_probe.py --format d81

.PHONY: ipc-lifecycle-probe
ipc-lifecycle-probe:
	$(PYTHON) tools/ipc_demo_probe.py --format d81 --lifecycle-only --restart-cycles 3
	$(PYTHON) tools/ipc_demo_probe.py --format d71 --lifecycle-only --restart-cycles 3
