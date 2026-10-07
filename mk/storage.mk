# SPDX-License-Identifier: GPL-3.0-or-later
STORAGE_BUILD := build/storage
# Separate write-backend probe. No new code or ABI is enabled in boot images.
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
# Actual service integration, compile-only until placement and trusted owner/
# exit hooks are qualified. Deliberately not in STORAGE_OBJECTS or boot targets.
WRITE_POLICY_BUILD := build/storage-write-policy
WRITE_POLICY_OBJECTS := $(addprefix $(WRITE_POLICY_BUILD)/,iec_service.o fs_namespace.o)
.PHONY: storage-write-policy
storage-write-policy: $(WRITE_POLICY_OBJECTS) storage-write-backend
$(WRITE_POLICY_BUILD):
	mkdir -p $@
$(WRITE_POLICY_OBJECTS): mk/storage.mk include/udeks/storage_write.h include/udeks/cbm_write.h include/udeks/fs_namespace.h
$(WRITE_POLICY_BUILD)/%.o: src/services/filesystem/%.c include/udeks/task_request.h | $(WRITE_POLICY_BUILD)
	$(CL65) $(CFLAGS_8502) -D UDEKS_STORAGE_WRITES -D UDEKS_IEC_WRITE --static-locals --code-name STORAGECODE -c -o $@ $<
.PHONY: filesystem-policy
# Compile/measure the #26 namespace contract without changing the boot image.
filesystem-policy: $(STORAGE_BUILD)/fs_namespace.o
$(STORAGE_BUILD)/fs_namespace.o: src/services/filesystem/fs_namespace.c include/udeks/fs_namespace.h include/udeks/task_request.h | $(STORAGE_BUILD)
	$(CL65) $(CFLAGS_8502) -D UDEKS_FS_READ_ONLY --static-locals --code-name STORAGECODE -c -o $@ $<
.PHONY: iec-eof-reference
iec-eof-reference: $(BUILD_IEC_DIRECTORY)/kernal-eof.prg
$(BUILD_IEC_DIRECTORY)/kernal-eof.o: bench/iec-directory/kernal-eof.s | $(BUILD_IEC_DIRECTORY)
	$(CA65) --cpu 6502 -o $@ $<
$(BUILD_IEC_DIRECTORY)/kernal-eof.bin: $(BUILD_IEC_DIRECTORY)/kernal-eof.o cfg/8502-iec-directory.cfg
	$(LD65) -C cfg/8502-iec-directory.cfg -o $@ $<
$(BUILD_IEC_DIRECTORY)/kernal-eof.prg: $(BUILD_IEC_DIRECTORY)/kernal-eof.bin
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@
STORAGE_OBJECTS := $(addprefix $(STORAGE_BUILD)/,iec_entry.o iec_service.o fs_namespace.o cbm_file.o iec_slow.o)
USER_MOUNT_BIN := $(BUILD_USER)/mount.bin
USER_MOUNT_UDEX := $(BUILD_USER)/mount.udx
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
$(USER_MOUNT_UDEX): $(USER_MOUNT_BIN) tools/build_udex.py
	$(PYTHON) tools/build_udex.py --cpu 8502 --load-address 0x0200 --entry-address 0x0200 $< $@
$(STORAGE_OBJECTS): mk/storage.mk include/udeks/cbm_file.h include/udeks/iec_slow.h
.PHONY: storage-service storage-vice-probe storage-shell-probe
storage-shell-probe:
	$(PYTHON) tools/storage_shell_probe.py
	$(PYTHON) tools/storage_shell_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/storage/shell-1571
storage-vice-probe:
	$(PYTHON) tools/storage_service_probe.py
storage-service: $(STORAGE_BUILD)/module.bin $(STORAGE_BUILD)/driver.bin $(STORAGE_BUILD)/policy.bin $(STORAGE_BUILD)/router.bin
$(STORAGE_BUILD):
	mkdir -p $@
$(STORAGE_BUILD)/%.o: src/services/filesystem/%.c include/udeks/task_request.h \
		include/udeks/cbm_directory.h include/udeks/iec_slow.h | $(STORAGE_BUILD)
	$(CL65) $(CFLAGS_8502) -c -o $@ $<
$(STORAGE_BUILD)/iec_entry.o: src/services/filesystem/iec_entry.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(STORAGE_BUILD)/iec_service.o: src/services/filesystem/iec_service.c include/udeks/task_request.h | $(STORAGE_BUILD)
	$(CL65) $(CFLAGS_8502) --static-locals --code-name STORAGECODE -c -o $@ $<
$(STORAGE_BUILD)/cbm_file.o: src/services/filesystem/cbm_file.c include/udeks/cbm_file.h include/udeks/iec_slow.h | $(STORAGE_BUILD)
	$(CL65) -t none --cpu 6502 --standard c99 -Os -I include --static-locals -c -o $@ $<
$(STORAGE_BUILD)/iec_slow.o: src/services/filesystem/iec_slow.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_STORAGE_MODULE -o $@ $<
$(STORAGE_BUILD)/module.bin $(STORAGE_BUILD)/driver.bin $(STORAGE_BUILD)/policy.bin $(STORAGE_BUILD)/module.map &: \
		$(STORAGE_OBJECTS) cfg/8502-storage.cfg
	$(CL65) -t none -C cfg/8502-storage.cfg -u _udeks_cbm_dos_error -m $(STORAGE_BUILD)/module.map \
		-o $(STORAGE_BUILD)/module.bin $(STORAGE_OBJECTS)
$(STORAGE_BUILD)/router.o: src/services/filesystem/iec_router.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(STORAGE_BUILD)/router.bin: $(STORAGE_BUILD)/router.o cfg/8502-storage-router.cfg
	$(LD65) -C cfg/8502-storage-router.cfg -o $@ $<

$(SCHEDULER_OVERLAY_PAYLOAD) $(SCHEDULER_OVERLAY_CONSTANTS): \
		$(STORAGE_BUILD)/module.bin $(STORAGE_BUILD)/policy.bin $(STORAGE_BUILD)/driver.bin \
		$(STORAGE_BUILD)/router.bin $(USER_USH_BIN) $(TASK_LOOKUP_BIN) tools/build_storage.py
