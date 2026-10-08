# SPDX-License-Identifier: GPL-3.0-or-later
# One normal boot layout; do not permit silent mixing with old resident builds.
ifneq ($(origin DISK_TIME),undefined)
$(error DISK_TIME is retired: normal make boot now loads TIME.SVC)
endif
TIME_RESIDENT_OBJECTS := $(BUILD_8502)/time-slot.o $(BUILD_8502)/time-resident.o
TIME_LINK_IMPORTS := -u _udeks_time_slot_request -u _udeks_time_slot_state -u _udeks_service_start_phase -u _udeks_service_start_result
TIME_ROUTER_FLAGS := -D UDEKS_DISK_TIME
TIME_BINDING_FLAGS := --kernel-map $(KERNEL_MAP)
BOOT_RC := user/etc/rc
SERVICE_BOOT_FILES := build/services/command/SVC.BIN build/services/time/TIME.SVC
SERVICE_DISK_FLAGS := --command SVC=build/services/command/SVC.BIN --data-file TIME.SVC=build/services/time/TIME.SVC --d71-full-capacity
$(BUILD_8502)/service_registry.s: CFLAGS_8502 += -D UDEKS_SERVICE_BOOT_SPLIT
$(BUILD_8502)/syscall_gate.o: ASFLAGS_8502 += -D UDEKS_DISK_TIME
# Recompile flag-sensitive outputs when upgrading an existing build tree.
.PHONY: service-boot service-boot-probe service-layout-check service-rebuild-check service-migration-check
service-boot: boot
service-rebuild-check: boot service-layout-check
	$(PYTHON) tools/build_service_boot.py
service-migration-check: boot service-layout-check
	$(PYTHON) tools/check_service_migration.py
service-boot-probe:
	$(PYTHON) tools/service_boot_probe.py
service-layout-check: $(KERNEL_BIN) $(PANIC_PROBE_KERNEL_BIN) time-module
	$(PYTHON) tools/default_service_layout.py
$(BUILD_8502)/time-slot.o: src/services/module/time_slot.s src/services/module/time_slot.inc | $(BUILD_8502)
	$(CA65) --cpu 6502 -D UDEKS_DISK_TIME -o $@ $<
$(BUILD_8502)/time-resident.o: src/services/time/resident.c include/udeks/time.h | $(BUILD_8502)
	$(CL65) $(CFLAGS_8502) -c -o $@ $<
.PHONY: time-module time-module-check time-module-placement time-slot-check service-start-probe time-overlay-check service-command service-request-check
service-request-check: time-module
	$(PYTHON) tools/check_service_request.py
service-command: build/services/command/SVC.BIN
build/services/command/SVC.BIN: user/bin/svc.c user/lib/service_request.s user/include/udeks/service.h \
        user/lib/filesystem.c user/lib/filesystem_meta.c user/lib/error_string.c user/lib/fs_request.s \
        user/lib/entry.s user/lib/syscall.s user/include/udeks/program.h include/udeks/task_request.h \
        cfg/8502-user-app1.cfg tools/build_console_example.py tools/build_udex.py mk/services.mk
	$(PYTHON) tools/build_console_example.py --source user/bin/svc.c --name SVC --services --static-locals --output build/services/command
time-module: build/services/time/TIME.SVC
time-module-check: time-module
	$(PYTHON) tools/check_time_module.py
time-module-placement: service-layout-check
time-slot-check: time-module
	$(PYTHON) tools/check_time_slot.py
service-start-probe:
	$(PYTHON) tools/service_start_probe.py
time-overlay-check: service-layout-check

build/services/time/TIME.SVC build/services/time/time.map build/services/time/layout.json &: \
        src/services/time/time.c src/services/time/module.s \
        src/services/time/clock_set.inc src/services/time/runtime.s \
        include/udeks/time.h include/udeks/capability.h \
        cfg/8502-time-module.cfg tools/service_image.py tools/build_time_module.py
	$(PYTHON) tools/build_time_module.py

$(BUILD_8502)/syscall_gate.o: src/services/time/clock_set.inc
$(BUILD_8502)/syscall_gate.o: src/services/module/request.inc src/services/module/time_slot.inc

build/services/time/time-slot.o: src/services/module/time_slot.s src/services/module/time_slot.inc
	mkdir -p $(@D)
	ca65 --cpu 6502 -o $@ $<
