# SPDX-License-Identifier: GPL-3.0-or-later
STORAGE_BUILD := build/storage
STORAGE_OBJECTS := $(addprefix $(STORAGE_BUILD)/,iec_entry.o iec_service.o cbm_directory.o iec_slow.o)
USER_MOUNT_BIN := $(BUILD_USER)/mount.bin
USER_MOUNT_UDEX := $(BUILD_USER)/mount.udx
USER_FILETOOLS_BIN := $(BUILD_USER)/filetools.bin
USER_FILETOOLS_UDEX := $(BUILD_USER)/filetools.udx
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
$(STORAGE_OBJECTS): mk/storage.mk
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
$(STORAGE_BUILD)/iec_slow.o: src/services/filesystem/iec_slow.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -D UDEKS_STORAGE_MODULE -o $@ $<
$(STORAGE_BUILD)/module.bin $(STORAGE_BUILD)/driver.bin $(STORAGE_BUILD)/policy.bin $(STORAGE_BUILD)/module.map &: \
		$(STORAGE_OBJECTS) cfg/8502-storage.cfg
	$(CL65) -t none -C cfg/8502-storage.cfg -m $(STORAGE_BUILD)/module.map \
		-o $(STORAGE_BUILD)/module.bin $(STORAGE_OBJECTS)
$(STORAGE_BUILD)/router.o: src/services/filesystem/iec_router.s | $(STORAGE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(STORAGE_BUILD)/router.bin: $(STORAGE_BUILD)/router.o cfg/8502-storage-router.cfg
	$(LD65) -C cfg/8502-storage-router.cfg -o $@ $<

$(SCHEDULER_OVERLAY_PAYLOAD) $(SCHEDULER_OVERLAY_CONSTANTS): \
		$(STORAGE_BUILD)/module.bin $(STORAGE_BUILD)/policy.bin $(STORAGE_BUILD)/driver.bin \
		$(STORAGE_BUILD)/router.bin $(USER_USH_BIN) tools/build_storage.py
