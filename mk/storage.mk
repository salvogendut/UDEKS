# SPDX-License-Identifier: GPL-3.0-or-later
STORAGE_BUILD := build/storage
NAMESPACE_BUILD := build/bench/storage-namespace
NAMESPACE_RENAMES := $(foreach fn,resolve device classify physical consider,-D udeks_fs_$(fn)=reference_$(fn))
.PHONY: storage-namespace-check storage-mutation-layout
storage-mutation-layout: placement-check-guard storage-service
	$(PYTHON) tools/storage_mutation_layout.py
storage-namespace-check: $(NAMESPACE_BUILD)/check $(NAMESPACE_BUILD)/negative
	sim65 $(NAMESPACE_BUILD)/check > $(NAMESPACE_BUILD)/check.log
	cat $(NAMESPACE_BUILD)/check.log
	@if sim65 $(NAMESPACE_BUILD)/negative > $(NAMESPACE_BUILD)/negative.log 2>&1; then \
		echo "namespace oracle accepted a broken rejection path" >&2; exit 1; fi
	rg -q '^FAIL resolve ' $(NAMESPACE_BUILD)/negative.log
$(NAMESPACE_BUILD):
	mkdir -p $@
$(NAMESPACE_BUILD)/reference.o: src/services/filesystem/fs_namespace.c include/udeks/fs_namespace.h | $(NAMESPACE_BUILD)
	$(CL65) -t sim6502 --standard c99 -Os --static-locals -I include $(NAMESPACE_RENAMES) -c -o $@ $<
$(NAMESPACE_BUILD)/namespace.o: src/services/filesystem/namespace_6502.s | $(NAMESPACE_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_NAMESPACE_TEST -o $@ $<
$(NAMESPACE_BUILD)/negative.o: src/services/filesystem/namespace_6502.s | $(NAMESPACE_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_NAMESPACE_TEST -D UDEKS_NAMESPACE_NEGATIVE -o $@ $<
$(NAMESPACE_BUILD)/check.o: bench/storage-namespace/check.c include/udeks/fs_namespace.h | $(NAMESPACE_BUILD)
	$(CL65) -t sim6502 --standard c99 -Os --static-locals -I include -c -o $@ $<
$(NAMESPACE_BUILD)/check: $(addprefix $(NAMESPACE_BUILD)/,check.o namespace.o reference.o)
	$(CL65) -t sim6502 -m $(NAMESPACE_BUILD)/check.map -o $@ $^
$(NAMESPACE_BUILD)/negative: $(addprefix $(NAMESPACE_BUILD)/,check.o negative.o reference.o)
	$(CL65) -t sim6502 -o $@ $^
# Private mutation backend qualification. Not installed in the storage module:
# the service preflight/placement and public command ABI are a later increment.
MUTATE_BUILD := build/bench/iec-mutate
MUTATE_FLAGS := -t none --cpu 6502 --standard c99 -Os -I include --static-locals -D UDEKS_IEC_WRITE -D UDEKS_IEC_MUTATE -D UDEKS_MUTATE_PROBE
MUTATE_OBJECTS := $(addprefix $(MUTATE_BUILD)/,entry.o main.o cbm_mutate.o cbm_file.o cbm_write.o iec_slow.o)
.PHONY: storage-mutate-backend storage-mutate-probe
storage-mutate-backend: $(MUTATE_BUILD)/mutate.prg
storage-mutate-probe:
	$(PYTHON) tools/storage_mutate_probe.py
$(MUTATE_BUILD):
	mkdir -p $@
$(MUTATE_OBJECTS): mk/storage.mk include/udeks/cbm_mutate.h include/udeks/iec_slow.h
$(MUTATE_BUILD)/entry.o: bench/iec-write/entry.s | $(MUTATE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(MUTATE_BUILD)/main.o: bench/iec-mutate/main.c | $(MUTATE_BUILD)
	$(CL65) $(MUTATE_FLAGS) -c -o $@ $<
$(MUTATE_BUILD)/cbm_mutate.o: src/services/filesystem/cbm_mutate.c | $(MUTATE_BUILD)
	$(CL65) $(MUTATE_FLAGS) -c -o $@ $<
$(MUTATE_BUILD)/cbm_file.o: src/services/filesystem/cbm_file.c include/udeks/cbm_file.h | $(MUTATE_BUILD)
	$(CL65) $(MUTATE_FLAGS) -c -o $@ $<
$(MUTATE_BUILD)/cbm_write.o: src/services/filesystem/cbm_write.c include/udeks/cbm_write.h | $(MUTATE_BUILD)
	$(CL65) $(MUTATE_FLAGS) -c -o $@ $<
$(MUTATE_BUILD)/iec_slow.o: src/services/filesystem/iec_slow.s | $(MUTATE_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_IEC_WRITE -D UDEKS_IEC_MUTATE -D UDEKS_MUTATE_PROBE -o $@ $<
$(MUTATE_BUILD)/mutate.bin: $(MUTATE_OBJECTS) cfg/8502-iec-write.cfg
	$(CL65) -t none -C cfg/8502-iec-write.cfg -m $(MUTATE_BUILD)/mutate.map -o $@ $(MUTATE_OBJECTS)
$(MUTATE_BUILD)/mutate.prg: $(MUTATE_BUILD)/mutate.bin tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@
# Separate backend qualification; public writes use the guarded boot service.
WRITE_BUILD := build/bench/iec-write
WRITE_CFLAGS := -t none --cpu 6502 --standard c99 -Os -I include --static-locals -D UDEKS_IEC_WRITE
WRITE_OBJECTS := $(addprefix $(WRITE_BUILD)/,entry.o main.o cbm_write.o cbm_file.o iec_slow.o)
.PHONY: storage-write-backend storage-write-probe
storage-write-backend: $(WRITE_BUILD)/write.prg
storage-write-probe: storage-write-backend
	$(PYTHON) tools/storage_write_probe.py
$(WRITE_BUILD):
	mkdir -p $@
$(WRITE_BUILD)/entry.o: bench/iec-write/entry.s | $(WRITE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(WRITE_BUILD)/main.o: bench/iec-write/main.c include/udeks/cbm_write.h | $(WRITE_BUILD)
	$(CL65) $(WRITE_CFLAGS) -c -o $@ $<
$(WRITE_BUILD)/%.o: src/services/filesystem/%.c include/udeks/cbm_write.h include/udeks/iec_slow.h include/udeks/cbm_file.h | $(WRITE_BUILD)
	$(CL65) $(WRITE_CFLAGS) -c -o $@ $<
$(WRITE_BUILD)/iec_slow.o: src/services/filesystem/iec_slow.s | $(WRITE_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_IEC_WRITE -o $@ $<
$(WRITE_BUILD)/write.bin: $(WRITE_OBJECTS) cfg/8502-iec-write.cfg
	$(CL65) -t none -C cfg/8502-iec-write.cfg -m $(WRITE_BUILD)/write.map -o $@ $(WRITE_OBJECTS)
$(WRITE_BUILD)/write.prg: $(WRITE_BUILD)/write.bin tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@
$(WRITE_OBJECTS): mk/storage.mk
# Separate policy/placement experiments, retained for reproducibility.
WRITE_POLICY_BUILD := build/storage-write-policy
WRITE_POLICY_OBJECTS := $(addprefix $(WRITE_POLICY_BUILD)/,iec_service.o fs_namespace.o)
.PHONY: storage-write-policy
storage-write-policy: $(WRITE_POLICY_OBJECTS) storage-write-backend
$(WRITE_POLICY_BUILD):
	mkdir -p $@
$(WRITE_POLICY_OBJECTS): mk/storage.mk include/udeks/storage_write.h include/udeks/cbm_write.h include/udeks/fs_namespace.h
$(WRITE_POLICY_BUILD)/%.o: src/services/filesystem/%.c include/udeks/task_request.h | $(WRITE_POLICY_BUILD)
	$(CL65) $(CFLAGS_8502) -D UDEKS_STORAGE_WRITES -D UDEKS_IEC_WRITE --static-locals --code-name STORAGECODE -c -o $@ $<
# Candidate placement only; never consumed by boot/disk image targets.
WRITE_PLACEMENT_BUILD := build/storage-write-placement
WRITE_PLACEMENT_OBJECTS := $(addprefix $(WRITE_PLACEMENT_BUILD)/,fs_namespace.o cbm_file.o cbm_write.o no-caller.o)
.PHONY: storage-write-placement
storage-write-placement: $(WRITE_PLACEMENT_BUILD)/module.bin
$(WRITE_PLACEMENT_BUILD):
	mkdir -p $@
$(WRITE_PLACEMENT_OBJECTS): mk/storage.mk include/udeks/storage_write.h
$(WRITE_PLACEMENT_BUILD)/fs_namespace.o: src/services/filesystem/fs_namespace.c include/udeks/fs_namespace.h | $(WRITE_PLACEMENT_BUILD)
	$(CL65) $(WRITE_CFLAGS) -D UDEKS_STORAGE_HIGH --code-name STORAGEHIGH -c -o $@ $<
$(WRITE_PLACEMENT_BUILD)/cbm_file.o: src/services/filesystem/cbm_file.c include/udeks/cbm_file.h | $(WRITE_PLACEMENT_BUILD)
	$(CL65) $(WRITE_CFLAGS) -D UDEKS_STORAGE_HIGH -c -o $@ $<
$(WRITE_PLACEMENT_BUILD)/cbm_write.o: src/services/filesystem/cbm_write.c include/udeks/cbm_write.h | $(WRITE_PLACEMENT_BUILD)
	$(CL65) $(WRITE_CFLAGS) -D UDEKS_STORAGE_HIGH --code-name STORAGECODE -c -o $@ $<
$(WRITE_PLACEMENT_BUILD)/no-caller.o: bench/storage-window/no-caller.s | $(WRITE_PLACEMENT_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(WRITE_PLACEMENT_BUILD)/iec_slow.o: src/services/filesystem/iec_slow.s mk/storage.mk | $(WRITE_PLACEMENT_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_STORAGE_MODULE -D UDEKS_IEC_WRITE -o $@ $<
$(WRITE_PLACEMENT_BUILD)/module.bin $(WRITE_PLACEMENT_BUILD)/policy.bin $(WRITE_PLACEMENT_BUILD)/driver.bin $(WRITE_PLACEMENT_BUILD)/hidden.bin $(WRITE_PLACEMENT_BUILD)/module.map &: \
		$(WRITE_PLACEMENT_OBJECTS) $(WRITE_POLICY_BUILD)/iec_service.o $(STORAGE_BUILD)/iec_entry.o $(WRITE_PLACEMENT_BUILD)/iec_slow.o cfg/8502-storage-write-candidate.cfg
	$(CL65) -t none -C cfg/8502-storage-write-candidate.cfg -m $(WRITE_PLACEMENT_BUILD)/module.map -o $(WRITE_PLACEMENT_BUILD)/module.bin $(filter %.o,$^)
STORAGE_WINDOW_BUILD := build/bench/storage-window
WRITE_LEASE_BUILD := build/storage-write-lease
.PHONY: storage-write-lease
storage-write-lease: $(WRITE_LEASE_BUILD)/module.bin
$(WRITE_LEASE_BUILD):
	mkdir -p $@
$(WRITE_LEASE_BUILD)/iec_service.o: src/services/filesystem/iec_service.c include/udeks/storage_write.h mk/storage.mk | $(WRITE_LEASE_BUILD)
	$(CL65) $(CFLAGS_8502) -D UDEKS_STORAGE_WRITES -D UDEKS_IEC_WRITE -D UDEKS_STORAGE_LEASE --static-locals --code-name STORAGECODE -c -o $@ $<
$(WRITE_LEASE_BUILD)/iec_lease.o: src/services/filesystem/iec_lease.s | $(WRITE_LEASE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(WRITE_LEASE_BUILD)/module.bin $(WRITE_LEASE_BUILD)/policy.bin $(WRITE_LEASE_BUILD)/driver.bin $(WRITE_LEASE_BUILD)/hidden.bin $(WRITE_LEASE_BUILD)/module.map &: \
		$(filter-out $(WRITE_PLACEMENT_BUILD)/no-caller.o,$(WRITE_PLACEMENT_OBJECTS)) $(WRITE_LEASE_BUILD)/iec_service.o $(WRITE_LEASE_BUILD)/iec_lease.o $(WRITE_PLACEMENT_BUILD)/iec_slow.o cfg/8502-storage-write-lease.cfg
	$(CL65) -t none -C cfg/8502-storage-write-lease.cfg -m $(WRITE_LEASE_BUILD)/module.map -o $(WRITE_LEASE_BUILD)/module.bin $(filter %.o,$^)
STORAGE_LEASE_PROBE := build/bench/storage-lease
.PHONY: storage-lease-probe
storage-lease-probe: $(STORAGE_LEASE_PROBE)/probe.prg
$(STORAGE_LEASE_PROBE):
	mkdir -p $@
$(STORAGE_LEASE_PROBE)/main.o: bench/storage-lease/main.c include/udeks/storage_write.h include/udeks/task_request.h | $(STORAGE_LEASE_PROBE)
	$(CL65) $(CFLAGS_8502) --static-locals -c -o $@ $<
$(STORAGE_LEASE_PROBE)/entry.o: bench/storage-lease/entry.s $(addprefix $(WRITE_LEASE_BUILD)/,module.bin policy.bin driver.bin hidden.bin) | $(STORAGE_LEASE_PROBE)
	$(CA65) --cpu 6502 -o $@ $<
$(STORAGE_LEASE_PROBE)/probe.bin: $(STORAGE_LEASE_PROBE)/entry.o $(STORAGE_LEASE_PROBE)/main.o bench/storage-lease/probe.cfg
	$(CL65) -t none -C bench/storage-lease/probe.cfg -m $(STORAGE_LEASE_PROBE)/probe.map -o $@ $(filter %.o,$^)
$(STORAGE_LEASE_PROBE)/probe.prg: $(STORAGE_LEASE_PROBE)/probe.bin tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@
.PHONY: storage-window storage-window-probe
storage-window: $(STORAGE_WINDOW_BUILD)/probe.prg storage-write-placement
storage-window-probe: storage-window
	$(PYTHON) tools/storage_window_probe.py
$(STORAGE_WINDOW_BUILD):
	mkdir -p $@
$(STORAGE_WINDOW_BUILD)/probe.o: bench/storage-window/probe.s src/8502/nmi-common.inc | $(STORAGE_WINDOW_BUILD)
	$(CA65) --cpu 6502 -I src/8502 -o $@ $<
$(STORAGE_WINDOW_BUILD)/probe.bin: $(STORAGE_WINDOW_BUILD)/probe.o bench/storage-window/probe.cfg
	$(LD65) -C bench/storage-window/probe.cfg -m $(STORAGE_WINDOW_BUILD)/probe.map -o $@ $<
$(STORAGE_WINDOW_BUILD)/probe.prg: $(STORAGE_WINDOW_BUILD)/probe.bin tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@
.PHONY: filesystem-policy
# The C implementation remains the policy oracle; this ABI-compatible
# implementation fits the same guarded service regions with more headroom.
filesystem-policy: $(STORAGE_BUILD)/fs_namespace.o
$(STORAGE_BUILD)/fs_namespace.o: src/services/filesystem/namespace_6502.s include/udeks/fs_namespace.h include/udeks/task_request.h mk/storage.mk | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
.PHONY: iec-eof-reference
iec-eof-reference: $(BUILD_IEC_DIRECTORY)/kernal-eof.prg
$(BUILD_IEC_DIRECTORY)/kernal-eof.o: bench/iec-directory/kernal-eof.s | $(BUILD_IEC_DIRECTORY)
	$(CA65) --cpu 6502 -o $@ $<
$(BUILD_IEC_DIRECTORY)/kernal-eof.bin: $(BUILD_IEC_DIRECTORY)/kernal-eof.o cfg/8502-iec-directory.cfg
	$(LD65) -C cfg/8502-iec-directory.cfg -o $@ $<
$(BUILD_IEC_DIRECTORY)/kernal-eof.prg: $(BUILD_IEC_DIRECTORY)/kernal-eof.bin
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@
STORAGE_OBJECTS := $(addprefix $(STORAGE_BUILD)/,iec_lease.o iec_context.o iec_service.o fs_namespace.o cbm_file.o cbm_write.o iec_slow.o)
USER_MOUNT_BIN := $(BUILD_USER)/mount.bin
USER_MOUNT_UDEX := $(BUILD_USER)/mount.udx
USER_RECOVERY_MOUNT_UDEX := $(BUILD_USER)/mount-recovery.udx
USER_SAVE_UDEX := $(BUILD_USER)/save.udx
USER_FILETOOLS_BIN := $(BUILD_USER)/filetools.bin
USER_FILETOOLS_UDEX := $(BUILD_USER)/filetools.udx
USER_SYSINFO_UDEX := $(BUILD_USER)/sysinfo.udx
USER_DIAGNOSTICS_UDEX := $(BUILD_USER)/diagnostics.udx
$(BUILD_USER)/diagnostics.o: user/bin/diagnostics.c include/udeks/service_control.h include/udeks/task_request.h | $(BUILD_USER)
	$(CL65) $(CFLAGS_8502) --static-locals -I user/include -c -o $@ $<
$(BUILD_USER)/diagnostics_request.o: user/lib/file_request.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -D UDEKS_FILE_REQUEST_MINOR=7 -o $@ $<
$(BUILD_USER)/diagnostics.bin: $(USER_ENTRY_OBJ) $(USER_SYSCALL_OBJ) $(BUILD_USER)/diagnostics.o $(BUILD_USER)/diagnostics_request.o cfg/8502-user-app1.cfg
	$(CL65) -t none -C cfg/8502-user-app1.cfg -m $(BUILD_USER)/diagnostics.map -o $@ $(filter %.o,$^)
$(USER_DIAGNOSTICS_UDEX): $(BUILD_USER)/diagnostics.bin tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 --entry-address 0x0200 --bss-size 0x0040 $< $@
$(BUILD_USER)/sysinfo.o: user/bin/sysinfo.c user/include/udeks/program.h include/udeks/task_request.h include/udeks/task_state.h include/udeks/capability.h | $(BUILD_USER)
	$(CL65) $(CFLAGS_8502) --static-locals -I user/include -c -o $@ $<
$(BUILD_USER)/sysinfo_request.o: user/lib/file_request.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -D UDEKS_FILE_REQUEST_MINOR=6 -o $@ $<
$(BUILD_USER)/sysinfo.bin: $(USER_ENTRY_OBJ) $(USER_SYSCALL_OBJ) $(BUILD_USER)/sysinfo.o $(BUILD_USER)/sysinfo_request.o cfg/8502-user-app1.cfg
	$(CL65) -t none -C cfg/8502-user-app1.cfg -m $(BUILD_USER)/sysinfo.map -o $@ $(filter %.o,$^)
$(USER_SYSINFO_UDEX): $(BUILD_USER)/sysinfo.bin tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 --entry-address 0x0200 --bss-size 0x0040 $< $@
.PHONY: filetools
filetools: $(USER_FILETOOLS_UDEX)
$(BUILD_USER)/filetools.o: user/bin/filetools.c user/include/udeks/program.h include/udeks/task_request.h | $(BUILD_USER)
	$(CL65) $(CFLAGS_8502) --static-locals -I user/include -c -o $@ $<
$(BUILD_USER)/file_request.o: user/lib/file_request.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<
$(USER_FILETOOLS_BIN): $(USER_ENTRY_OBJ) $(USER_SYSCALL_OBJ) $(BUILD_USER)/filetools.o $(BUILD_USER)/file_request.o cfg/8502-user-app1.cfg
	$(CL65) -t none -C cfg/8502-user-app1.cfg -m $(BUILD_USER)/filetools.map -o $@ $(filter %.o,$^)
$(USER_FILETOOLS_UDEX): $(USER_FILETOOLS_BIN) tools/build_udex.py mk/storage.mk
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 --entry-address 0x0200 --bss-size 0x0040 $< $@
.PHONY: mount-command
mount-command: $(USER_MOUNT_UDEX)
$(BUILD_USER)/mount.o: user/bin/mount.c user/include/udeks/program.h include/udeks/task_request.h | $(BUILD_USER)
	$(CL65) $(CFLAGS_8502) -I user/include -c -o $@ $<
$(BUILD_USER)/mount_request.o: user/lib/mount_request.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<
$(USER_MOUNT_BIN): $(USER_ENTRY_OBJ) $(USER_SYSCALL_OBJ) $(BUILD_USER)/mount.o $(BUILD_USER)/mount_request.o cfg/8502-user-app1.cfg
	$(CL65) -t none -C cfg/8502-user-app1.cfg -m $(BUILD_USER)/mount.map -o $@ $(filter %.o,$^)
$(USER_RECOVERY_MOUNT_UDEX): $(USER_MOUNT_BIN) tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 --entry-address 0x0200 $< $@
$(BUILD_USER)/mount_rw.o: user/bin/mount_rw.c user/include/udeks/program.h | $(BUILD_USER)
	$(CL65) $(CFLAGS_8502) -I user/include -c -o $@ $<
$(BUILD_USER)/mount_rw_request.o: user/lib/mount_rw_request.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<
$(BUILD_USER)/error_string.o: user/lib/error_string.c user/include/udeks/program.h | $(BUILD_USER)
	$(CL65) $(CFLAGS_8502) -I user/include -c -o $@ $<
$(BUILD_USER)/mount-rw.bin: $(USER_ENTRY_OBJ) $(USER_SYSCALL_OBJ) $(BUILD_USER)/mount_rw.o $(BUILD_USER)/mount_rw_request.o $(BUILD_USER)/error_string.o cfg/8502-user-app1.cfg
	$(CL65) -t none -C cfg/8502-user-app1.cfg -m $(BUILD_USER)/mount-rw.map -o $@ $(filter %.o,$^)
$(USER_MOUNT_UDEX): $(BUILD_USER)/mount-rw.bin tools/build_udex.py mk/storage.mk
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 --entry-address 0x0200 $< $@
$(USER_SAVE_UDEX): user/bin/save.c user/lib/filesystem.c user/lib/filesystem_meta.c \
        user/lib/fs_request.s user/lib/error_string.c user/lib/entry.s user/lib/syscall.s \
        user/include/udeks/program.h include/udeks/task_request.h cfg/8502-user-app1.cfg \
        tools/build_console_example.py tools/build_udex.py tools/gen_capability_imports.py \
        mk/storage.mk | $(BUILD_USER)
	$(PYTHON) tools/build_console_example.py --filesystem --static-locals --source user/bin/save.c --name SAVE --output $(BUILD_USER)/save
	cp $(BUILD_USER)/save/SAVE.BIN $@
$(BUILD_USER)/fs_request.o: user/lib/fs_request.s | $(BUILD_USER)
	$(CA65) --cpu 6502 -o $@ $<
$(BUILD_USER)/filesystem_meta.o: user/lib/filesystem_meta.c user/include/udeks/program.h include/udeks/task_request.h | $(BUILD_USER)
	$(CL65) $(CFLAGS_8502) -I user/include -c -o $@ $<
$(USER_LS_BIN): $(BUILD_USER)/fs_request.o $(BUILD_USER)/filesystem_meta.o
$(STORAGE_OBJECTS): mk/storage.mk include/udeks/cbm_file.h include/udeks/iec_slow.h \
	include/udeks/storage_write.h include/udeks/cbm_write.h include/udeks/fs_namespace.h
.PHONY: storage-service storage-vice-probe storage-shell-probe
storage-shell-probe:
	$(PYTHON) tools/storage_shell_probe.py
	$(PYTHON) tools/storage_shell_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/storage/shell-1571
storage-vice-probe:
	$(PYTHON) tools/storage_service_probe.py
storage-service: $(STORAGE_BUILD)/module.bin $(STORAGE_BUILD)/driver.bin $(STORAGE_BUILD)/policy.bin $(STORAGE_BUILD)/hidden.bin $(STORAGE_BUILD)/router.bin $(STORAGE_BUILD)/install.bin
$(STORAGE_BUILD):
	mkdir -p $@
$(STORAGE_BUILD)/%.o: src/services/filesystem/%.c include/udeks/task_request.h \
		include/udeks/cbm_directory.h include/udeks/iec_slow.h | $(STORAGE_BUILD)
	$(CL65) $(CFLAGS_8502) -c -o $@ $<
$(STORAGE_BUILD)/iec_entry.o: src/services/filesystem/iec_entry.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(STORAGE_BUILD)/iec_service.o: src/services/filesystem/iec_service.c include/udeks/task_request.h | $(STORAGE_BUILD)
	$(CL65) $(CFLAGS_8502) -D UDEKS_STORAGE_WRITES -D UDEKS_IEC_WRITE -D UDEKS_STORAGE_LEASE --static-locals --code-name STORAGECODE -c -o $@ $<
$(STORAGE_BUILD)/cbm_file.o: src/services/filesystem/cbm_file.c include/udeks/cbm_file.h include/udeks/iec_slow.h | $(STORAGE_BUILD)
	$(CL65) $(WRITE_CFLAGS) -D UDEKS_STORAGE_HIGH -c -o $@ $<
$(STORAGE_BUILD)/cbm_write.o: src/services/filesystem/cbm_write.c include/udeks/cbm_write.h | $(STORAGE_BUILD)
	$(CL65) $(WRITE_CFLAGS) -D UDEKS_STORAGE_HIGH --code-name STORAGECODE -c -o $@ $<
$(STORAGE_BUILD)/iec_lease.o: src/services/filesystem/iec_lease.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_STORAGE_CONTEXT -o $@ $<
$(STORAGE_BUILD)/iec_context.o: src/services/filesystem/iec_context.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(STORAGE_BUILD)/install.o: src/boot/storage-install.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(STORAGE_BUILD)/install.bin: $(STORAGE_BUILD)/install.o cfg/8502-storage-install.cfg
	$(LD65) -C cfg/8502-storage-install.cfg -o $@ $<
$(STORAGE_BUILD)/iec_slow.o: src/services/filesystem/iec_slow.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_STORAGE_MODULE -D UDEKS_IEC_WRITE -o $@ $<
$(STORAGE_BUILD)/module.bin $(STORAGE_BUILD)/driver.bin $(STORAGE_BUILD)/policy.bin $(STORAGE_BUILD)/hidden.bin $(STORAGE_BUILD)/module.map &: \
		$(STORAGE_OBJECTS) cfg/8502-storage.cfg
	$(CL65) -t none -C cfg/8502-storage.cfg -u _udeks_cbm_dos_error -u _udeks_storage_generations -u _udeks_storage_cleanup_error -m $(STORAGE_BUILD)/module.map \
		-o $(STORAGE_BUILD)/module.bin $(STORAGE_OBJECTS)
$(STORAGE_BUILD)/router.o: src/services/filesystem/iec_router.s $(BUILD_8502)/disk-loader-bindings.inc | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -I $(BUILD_8502) -o $@ $<
$(STORAGE_BUILD)/router.bin: $(STORAGE_BUILD)/router.o cfg/8502-storage-router.cfg
	$(LD65) -C cfg/8502-storage-router.cfg -o $@ $<

$(SCHEDULER_OVERLAY_PAYLOAD) $(SCHEDULER_OVERLAY_CONSTANTS): \
		$(STORAGE_BUILD)/module.bin $(STORAGE_BUILD)/policy.bin $(STORAGE_BUILD)/driver.bin \
		$(STORAGE_BUILD)/hidden.bin $(STORAGE_BUILD)/install.bin \
		$(STORAGE_BUILD)/router.bin $(USER_USH_BIN) $(TASK_LOOKUP_BIN) tools/build_storage.py

# Independent adversarial clients; never shipped on the normal system disk.
OWNER_BUILD := build/storage-owner
.PHONY: storage-owner-fixtures storage-owner-probe
storage-owner-fixtures:
	$(PYTHON) tools/build_console_example.py --source bench/storage-owner/foreground.c --name LEAK --output $(OWNER_BUILD)/foreground
	$(PYTHON) tools/build_graphical_example.py --source bench/storage-owner/holder.c --name HOLD --static-locals --export _owner_stage --export _owner_release --output $(OWNER_BUILD)/holder
	$(PYTHON) tools/build_graphical_example.py --source bench/storage-owner/parent.c --name PARENT --static-locals --export _parent_stage --export _parent_release --export _parent_error --export _parent_result --output $(OWNER_BUILD)/parent
	$(CA65) --cpu 6502 -o $(OWNER_BUILD)/child.o bench/storage-owner/child.s
	$(LD65) -C bench/storage-owner/child.cfg -o $(OWNER_BUILD)/child.bin $(OWNER_BUILD)/child.o
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 --entry-address 0x0200 $(OWNER_BUILD)/child.bin $(OWNER_BUILD)/CHILD.BIN
storage-owner-probe:
	$(PYTHON) tools/storage_owner_probe.py

FAILURE_BUILD := build/storage-failures
.PHONY: storage-failure-fixtures
storage-failure-fixtures:
	$(PYTHON) tools/build_console_example.py --filesystem --static-locals --source bench/storage-failures/foreground.c --name WLEAK --output $(FAILURE_BUILD)/foreground
	$(PYTHON) tools/build_graphical_example.py --source bench/storage-failures/holder.c --name WHOLD --static-locals --export _writer_stage --export _writer_release --export _writer_case --export _writer_errno --export _writer_written --export _writer_closed --output $(FAILURE_BUILD)/holder
	$(PYTHON) tools/build_graphical_example.py --source bench/storage-owner/parent.c --name PARENT --static-locals --export _parent_stage --export _parent_release --export _parent_error --export _parent_result --output $(FAILURE_BUILD)/parent
	$(CA65) --cpu 6502 -o $(FAILURE_BUILD)/child.o bench/storage-failures/child.s
	$(LD65) -C bench/storage-owner/child.cfg -o $(FAILURE_BUILD)/child.bin $(FAILURE_BUILD)/child.o
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 --entry-address 0x0200 $(FAILURE_BUILD)/child.bin $(FAILURE_BUILD)/CHILD.BIN
