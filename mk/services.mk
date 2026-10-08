# SPDX-License-Identifier: GPL-3.0-or-later
# First disk-service candidate; not a dependency of normal boot yet.
TIME_RESIDENT_OBJECTS := $(BUILD_8502)/time.o
BOOT_RC := user/etc/rc
ifeq ($(DISK_TIME),1)
ifeq ($(wildcard .udeks-service-candidate),)
$(error DISK_TIME is isolated: use make service-boot, not DISK_TIME=1 in a normal worktree)
endif
TIME_RESIDENT_OBJECTS := $(BUILD_8502)/time-slot.o $(BUILD_8502)/time-resident.o
TIME_LINK_IMPORTS := -u _udeks_time_slot_request -u _udeks_time_slot_state -u _udeks_service_start_phase -u _udeks_service_start_result
TIME_ROUTER_FLAGS := -D UDEKS_DISK_TIME
TIME_BINDING_FLAGS := --kernel-map $(KERNEL_MAP)
BOOT_RC := user/etc/rc-services
SERVICE_BOOT_FILES := build/services/command/SVC.BIN build/services/time/TIME.SVC
SERVICE_DISK_FLAGS := --command SVC=build/services/command/SVC.BIN --data-file TIME.SVC=build/services/time/TIME.SVC --d71-full-capacity
$(BUILD_8502)/service_registry.s: CFLAGS_8502 += -D UDEKS_SERVICE_BOOT_SPLIT
$(BUILD_8502)/syscall_gate.o: ASFLAGS_8502 += -D UDEKS_DISK_TIME
endif
.PHONY: service-boot service-boot-probe
service-boot: $(KERNEL_BIN) $(PANIC_PROBE_KERNEL_BIN)
	$(PYTHON) tools/build_service_boot.py
service-boot-probe:
	$(PYTHON) tools/service_boot_probe.py
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
time-module-placement: time-module build/services/time/time-slot.o $(KERNEL_BIN) $(PANIC_PROBE_KERNEL_BIN)
	$(PYTHON) tools/time_module_layout.py
time-slot-check: time-module
	$(PYTHON) tools/check_time_slot.py
service-start-probe:
	$(PYTHON) tools/service_start_probe.py
time-overlay-check: time-module $(KERNEL_BIN) $(PANIC_PROBE_KERNEL_BIN) $(BUILD_8502)/disk-loader-bindings.inc
	$(PYTHON) tools/build_time_overlay.py

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
