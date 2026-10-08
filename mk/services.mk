# SPDX-License-Identifier: GPL-3.0-or-later
# First disk-service candidate; not a dependency of normal boot yet.
.PHONY: time-module time-module-check time-module-placement time-slot-check service-start-probe time-overlay-check
time-module: build/services/time/TIME.SVC
time-module-check: time-module
	$(PYTHON) tools/check_time_module.py
time-module-placement: time-module build/services/time/time-slot.o $(KERNEL_BIN) $(PANIC_PROBE_KERNEL_BIN)
	$(PYTHON) tools/time_module_layout.py
time-slot-check: time-module
	$(PYTHON) tools/check_time_slot.py
service-start-probe:
	$(PYTHON) tools/service_start_probe.py
time-overlay-check: time-module $(KERNEL_BIN) $(PANIC_PROBE_KERNEL_BIN)
	$(PYTHON) tools/build_time_overlay.py

build/services/time/TIME.SVC build/services/time/time.map build/services/time/layout.json &: \
        src/services/time/time.c src/services/time/module.s \
        src/services/time/clock_set.inc src/services/time/runtime.s \
        include/udeks/time.h include/udeks/capability.h \
        cfg/8502-time-module.cfg tools/service_image.py tools/build_time_module.py
	$(PYTHON) tools/build_time_module.py

$(BUILD_8502)/syscall_gate.o: src/services/time/clock_set.inc

build/services/time/time-slot.o: src/services/module/time_slot.s src/services/module/time_slot.inc
	mkdir -p $(@D)
	ca65 --cpu 6502 -o $@ $<
